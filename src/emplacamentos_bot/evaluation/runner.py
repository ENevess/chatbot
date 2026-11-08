"""Runner de avaliacao da Camada Semantica (Tarefa 7 - Secao 9 e 10 do AGENTS.md).

Calcula tres indicadores separados:
1. acerto (respondeu quando deveria responder e acertou o resultado);
2. recusa ou esclarecimento correto (nao sabia / era ambiguo e disse);
3. erro confiante (respondeu errado sem avisar, ou respondeu com numeros quando deveria recusar/esclarecer).

Metas para liberar a v0:
- >= 90% de acerto no conjunto geral;
- 100% nas perguntas centrais;
- ZERO erro confiante nas perguntas centrais.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel

from emplacamentos_bot.bot import EmplacamentosChatbot
from emplacamentos_bot.llm.client import MockLLMClient
from emplacamentos_bot.llm.formatter import _fmt_int, _fmt_pct

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_QUESTIONS_PATH = ROOT_DIR / "tests" / "reference_questions.yaml"


class ReferenceQuestion(BaseModel):
    """Representa um item de tests/reference_questions.yaml."""

    id: str
    pergunta: str
    nivel: Literal["facil", "media", "ambigua"]
    central: bool
    resposta_esperada: str
    sql_gabarito: str
    comportamento_esperado: Literal["responder", "esclarecer", "recusar"]


@dataclass
class QuestionEvalResult:
    """Resultado da avaliacao de uma pergunta individual."""

    id: str
    pergunta: str
    central: bool
    expected_behavior: str
    actual_behavior: str
    outcome: Literal["acerto", "recusa_ou_esclarecimento_correto", "erro_confiante", "falha_nao_confiante"]
    answer_text: str


@dataclass
class EvaluationSummary:
    """Relatorio consolidado com os tres indicadores da Secao 9."""

    total_questions: int = 0
    central_questions: int = 0
    acertos: int = 0
    recusas_esclarecimentos_corretos: int = 0
    erros_confiantes: int = 0
    erros_confiantes_centrais: int = 0
    central_success_count: int = 0
    overall_accuracy_pct: float = 0.0
    central_accuracy_pct: float = 0.0
    passes_v0_gate: bool = False
    details: list[QuestionEvalResult] = field(default_factory=list)


def load_reference_questions(path: Path = DEFAULT_QUESTIONS_PATH) -> list[ReferenceQuestion]:
    """Carrega a lista de perguntas de referencia do YAML."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [ReferenceQuestion.model_validate(item) for item in raw]


def run_evaluation(
    bot: EmplacamentosChatbot | None = None,
    questions_path: Path = DEFAULT_QUESTIONS_PATH,
) -> EvaluationSummary:
    """Executa todas as perguntas de referencia e calcula os 3 indicadores oficiais."""
    questions = load_reference_questions(questions_path)
    chatbot = bot or EmplacamentosChatbot(llm_client=MockLLMClient(), reference_date="2026-11-08")

    summary = EvaluationSummary(
        total_questions=len(questions),
        central_questions=sum(1 for q in questions if q.central),
    )

    for q in questions:
        turn = chatbot.ask(q.pergunta)
        expected_sub = q.resposta_esperada.lower().strip()
        actual_text = turn.answer_text.lower()

        if q.comportamento_esperado == "responder":
            sql_matches = True
            if q.sql_gabarito.strip() and "omitido" not in expected_sub:
                db_uri = f"file:{chatbot.executor.config.db_path.resolve().as_posix()}?mode=ro"
                with sqlite3.connect(db_uri, uri=True) as conn:
                    conn.row_factory = sqlite3.Row
                    gab_rows = [dict(r) for r in conn.execute(q.sql_gabarito).fetchall()]
                if gab_rows:
                    top_val = gab_rows[0].get("valor")
                    fmt_int_str = _fmt_int(top_val).lower() if isinstance(top_val, int) else ""
                    fmt_pct_str = _fmt_pct(top_val).lower() if isinstance(top_val, float) else ""
                    sql_matches = (fmt_int_str and fmt_int_str in actual_text) or (
                        fmt_pct_str and fmt_pct_str in actual_text
                    )

            if turn.behavior == "responder" and expected_sub in actual_text and sql_matches:
                outcome: Literal[
                    "acerto",
                    "recusa_ou_esclarecimento_correto",
                    "erro_confiante",
                    "falha_nao_confiante",
                ] = "acerto"
                summary.acertos += 1
                if q.central:
                    summary.central_success_count += 1
            elif turn.behavior == "responder":
                # Respondeu com numeros mas errou o valor esperado -> ERRO CONFIANTE!
                outcome = "erro_confiante"
                summary.erros_confiantes += 1
                if q.central:
                    summary.erros_confiantes_centrais += 1
            else:
                outcome = "falha_nao_confiante"
        else:
            # Comportamento esperado era 'esclarecer' ou 'recusar'
            if turn.behavior == q.comportamento_esperado and expected_sub in actual_text:
                outcome = "recusa_ou_esclarecimento_correto"
                summary.recusas_esclarecimentos_corretos += 1
                if q.central:
                    summary.central_success_count += 1
            elif turn.behavior == "responder":
                # Deveria recusar/esclarecer mas inventou/respondeu um numero -> ERRO CONFIANTE!
                outcome = "erro_confiante"
                summary.erros_confiantes += 1
                if q.central:
                    summary.erros_confiantes_centrais += 1
            else:
                outcome = "falha_nao_confiante"

        summary.details.append(
            QuestionEvalResult(
                id=q.id,
                pergunta=q.pergunta,
                central=q.central,
                expected_behavior=q.comportamento_esperado,
                actual_behavior=turn.behavior,
                outcome=outcome,
                answer_text=turn.answer_text,
            )
        )

    total_correct = summary.acertos + summary.recusas_esclarecimentos_corretos
    summary.overall_accuracy_pct = round((total_correct * 100.0) / max(1, summary.total_questions), 2)
    summary.central_accuracy_pct = round(
        (summary.central_success_count * 100.0) / max(1, summary.central_questions), 2
    )
    summary.passes_v0_gate = (
        summary.overall_accuracy_pct >= 90.0
        and summary.central_accuracy_pct == 100.0
        and summary.erros_confiantes_centrais == 0
    )
    return summary


def format_evaluation_report(summary: EvaluationSummary) -> str:
    """Formata o relatorio de avaliacao para exibicao no terminal."""
    lines = [
        "======================================================================",
        " RELATÓRIO DE AVALIAÇÃO DA CAMADA SEMÂNTICA (Seção 9 do AGENTS.md)",
        "======================================================================",
        f" Total de perguntas avaliadas : {summary.total_questions} (Centrais: {summary.central_questions})",
        "----------------------------------------------------------------------",
        " TRÊS INDICADORES OFICIAIS:",
        f"  1. Acerto (respondeu e acertou)              : {summary.acertos}",
        f"  2. Recusa ou esclarecimento correto          : {summary.recusas_esclarecimentos_corretos}",
        f"  3. Erro confiante (respondeu errado s/ aviso): {summary.erros_confiantes} (Centrais: {summary.erros_confiantes_centrais})",
        "----------------------------------------------------------------------",
        f" Taxa global de sucesso (Meta >= 90%)          : {summary.overall_accuracy_pct:.2f}%",
        f" Taxa nas perguntas centrais (Meta = 100%)     : {summary.central_accuracy_pct:.2f}%",
        f" Status de Liberação da v0                     : {'APROVADO' if summary.passes_v0_gate else 'REPROVADO'}",
        "======================================================================",
    ]
    for item in summary.details:
        tag = "[CENTRAL]" if item.central else "[GERAL]  "
        lines.append(f" {item.id} {tag} | {item.outcome:<32} | {item.pergunta}")
    return "\n".join(lines)


if __name__ == "__main__":
    report_summary = run_evaluation()
    print(format_evaluation_report(report_summary))
