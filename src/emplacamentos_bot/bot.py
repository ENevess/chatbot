"""Orquestrador principal do Chatbot de Emplacamentos (Pipeline Secao 5 do AGENTS.md)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from emplacamentos_bot.compiler.sql_compiler import (
    AmbiguousQueryError,
    QuerySpec,
    SemanticValidationError,
    SQLCompiler,
)
from emplacamentos_bot.executor.safe_executor import (
    ExecutionResult,
    ExecutorConfig,
    SafeSQLExecutor,
)
from emplacamentos_bot.llm.client import LLMClient, create_llm_client
from emplacamentos_bot.llm.formatter import ResponseFormatter
from emplacamentos_bot.semantic.loader import SemanticCatalog, load_semantic_catalog


@dataclass
class BotTurnResult:
    """Resultado completo de uma interacao com o Chatbot."""

    question: str
    behavior: Literal["responder", "esclarecer", "recusar"]
    answer_text: str
    spec: QuerySpec | None = None
    sql: str | None = None
    rows: list[dict[str, Any]] = field(default_factory=list)
    privacy_suppressed: bool = False
    interaction_id: str = ""


class EmplacamentosChatbot:
    """Orquestra interpretacao (LLM/Mock), compilacao deterministica, execucao segura e redacao."""

    def __init__(
        self,
        catalog: SemanticCatalog | None = None,
        llm_client: LLMClient | None = None,
        executor_config: ExecutorConfig | None = None,
        reference_date: str = "2026-11-08",
    ) -> None:
        self.catalog = catalog or load_semantic_catalog()
        self.llm_client = llm_client or create_llm_client()
        self.compiler = SQLCompiler(self.catalog, reference_date=reference_date)
        self.executor = SafeSQLExecutor(
            allowed_tables=self.catalog.get_allowed_tables(),
            config=executor_config,
        )
        self.formatter = ResponseFormatter()
        self.pending_clarification_question: str | None = None

    def ask(self, question: str) -> BotTurnResult:
        """Executa o fluxo de 5 etapas da Secao 5 do AGENTS.md mantendo contexto de esclarecimento."""
        raw_input = question.strip()
        effective_question = raw_input
        if self.pending_clarification_question:
            # Se o usuario enviou uma resposta curta/complementar (< 45 caracteres), mescla com a pergunta anterior;
            # se enviou uma nova pergunta completa, substitui a pendente.
            if len(raw_input) < 45 and not raw_input.endswith("?"):
                effective_question = f"{self.pending_clarification_question} ({raw_input})"
            else:
                self.pending_clarification_question = None

        # 1 e 2. Interpretar a pergunta e mapear para QuerySpec estruturado (sem tocar no banco)
        spec = self.llm_client.interpret_question(effective_question, self.catalog)

        # 3. Compilar deterministicamente para SQL (ou capturar esclarecimento/recusa)
        try:
            compiled = self.compiler.compile(spec)
        except AmbiguousQueryError as exc:
            self.pending_clarification_question = effective_question
            ans_text = self.formatter.format_clarification(str(exc))
            turn_id = self.executor.log_audit(
                question=effective_question,
                spec_dict=spec.model_dump(),
                sql="",
                status="clarify",
                error_message=str(exc),
                answer_text=ans_text,
            )
            return BotTurnResult(
                question=effective_question,
                behavior="esclarecer",
                answer_text=ans_text,
                spec=spec,
                interaction_id=turn_id,
            )
        except SemanticValidationError as exc:
            self.pending_clarification_question = None
            ans_text = self.formatter.format_refusal(str(exc))
            turn_id = self.executor.log_audit(
                question=effective_question,
                spec_dict=spec.model_dump(),
                sql="",
                status="refuse",
                error_message=str(exc),
                answer_text=ans_text,
            )
            return BotTurnResult(
                question=effective_question,
                behavior="recusar",
                answer_text=ans_text,
                spec=spec,
                interaction_id=turn_id,
            )

        # Esclarecimento resolvido com sucesso: limpa estado pendente
        self.pending_clarification_question = None

        # 4. Executar o SQL com as protecoes da Secao 7 (allowlist, read-only, k-anonimato)
        exec_result: ExecutionResult = self.executor.execute(
            sql=compiled.sql,
            params=compiled.params,
            question=effective_question,
            spec_dict=spec.model_dump(),
        )

        # 5. Redigir a resposta no formato da Secao 8 (100% localmente, sem enviar dados ao LLM)
        answer_text = self.formatter.format_query_response(
            compiled=compiled,
            result=exec_result,
            min_k=self.executor.config.min_k_anonymity,
        )

        return BotTurnResult(
            question=effective_question,
            behavior="responder",
            answer_text=answer_text,
            spec=spec,
            sql=compiled.sql,
            rows=exec_result.rows,
            privacy_suppressed=exec_result.privacy_suppressed,
            interaction_id=exec_result.interaction_id,
        )
