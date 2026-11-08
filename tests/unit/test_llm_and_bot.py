"""Testes unitarios e de integracao offline do LLMClient (Mock + Claude) e Pipeline (Tarefa 5)."""

import json
from pathlib import Path

import pytest

from emplacamentos_bot.bot import EmplacamentosChatbot
from emplacamentos_bot.executor.safe_executor import ExecutorConfig
from emplacamentos_bot.llm.client import ClaudeLLMClient, MockLLMClient
from emplacamentos_bot.semantic.loader import load_semantic_catalog

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = ROOT_DIR / "data" / "emplacamentos_synthetic.db"


@pytest.fixture
def offline_bot(tmp_path: Path) -> EmplacamentosChatbot:
    """Instancia o chatbot completo usando MockLLMClient (100% sem rede)."""
    catalog = load_semantic_catalog()
    config = ExecutorConfig(
        db_path=DB_PATH,
        log_path=tmp_path / "bot_audit.jsonl",
        min_k_anonymity=5,
    )
    return EmplacamentosChatbot(
        catalog=catalog,
        llm_client=MockLLMClient(),
        executor_config=config,
        reference_date="2026-11-08",
    )


@pytest.mark.skipif(not DB_PATH.exists(), reason="Banco sintetico local nao encontrado")
def test_full_pipeline_runs_offline_and_formats_section8(offline_bot: EmplacamentosChatbot) -> None:
    """Pronto quando (Secao 10, Tarefa 5): o fluxo completo rodar sem rede e no formato da Secao 8."""
    res = offline_bot.ask("Quantos caminhões foram emplacados no último mês?")
    assert res.behavior == "responder"
    assert res.sql is not None
    # Verifica os 4 itens obrigatorios da Secao 8
    assert "1. **Resposta direta:**" in res.answer_text
    assert "2. **Período e filtros aplicados:**" in res.answer_text
    assert "último mês fechado (2026-10)" in res.answer_text
    assert "3. **Definição da métrica" in res.answer_text
    assert "4. **Privacidade:**" in res.answer_text


def test_bot_asks_clarification_when_period_missing(offline_bot: EmplacamentosChatbot) -> None:
    """Verifica a regra inegociavel #2: sem periodo informado, o bot pede esclarecimento."""
    res = offline_bot.ask("Quantos caminhões da DAF foram emplacados?")
    assert res.behavior == "esclarecer"
    assert "período" in res.answer_text.lower()


def test_bot_asks_clarification_when_dealer_type_ambiguous(offline_bot: EmplacamentosChatbot) -> None:
    """Verifica a regra #6: se pedir por dealer sem especificar DAF vs emplacamento, questiona."""
    res = offline_bot.ask("Qual o volume de emplacamentos por dealer em 2025?")
    assert res.behavior == "esclarecer"
    assert "Dealer DAF" in res.answer_text
    assert "Dealer de emplacamento" in res.answer_text


def test_bot_refuses_out_of_scope_and_unknown_metrics(offline_bot: EmplacamentosChatbot) -> None:
    """Verifica recusa educada para fora de escopo (previsao/PII) e metricas inexistentes (faturamento)."""
    res_scope = offline_bot.ask("Qual a previsão de emplacamentos para 2028?")
    assert res_scope.behavior == "recusar"

    res_metric = offline_bot.ask("Qual foi o faturamento médio das concessionárias em 2025?")
    assert res_metric.behavior == "recusar"


def test_claude_client_payload_contains_zero_database_data() -> None:
    """Garante que o payload preparado para o Claude contem apenas a pergunta e o catalogo semantico."""
    catalog = load_semantic_catalog()
    claude = ClaudeLLMClient(api_key="test-dummy-key", model="claude-3-5-sonnet-latest")
    payload = claude.build_messages_payload(
        question="Qual a participação de mercado da DAF em 2025?",
        catalog=catalog,
    )
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "temperature" not in payload
    assert "Qual a participação de mercado da DAF em 2025?" in serialized
    assert "volume_emplacamentos" in serialized
    # Garante que nenhuma string de cliente sintetico, VIN ou placa está no payload
    assert "TRANSPORTADORA SINTETICA" not in serialized
    assert "9BW" not in serialized


@pytest.mark.skipif(not DB_PATH.exists(), reason="Banco sintetico local nao encontrado")
def test_brand_share_within_specific_segment(offline_bot: EmplacamentosChatbot) -> None:
    """Garante que participacao de mercado de uma marca filtrada por segmento calcula corretamente."""
    res = offline_bot.ask("Qual a participação de mercado da DAF em 2026 apenas no segmento pesado?")
    assert res.behavior == "responder"
    assert res.spec is not None
    assert res.spec.metric == "participacao_mercado_marca"
    assert "DAF:" in res.answer_text
    assert "segmento=PESADO" in res.answer_text
    assert "marca=DAF" in res.answer_text


@pytest.mark.skipif(not DB_PATH.exists(), reason="Banco sintetico local nao encontrado")
def test_multi_turn_clarification_preserves_original_context(offline_bot: EmplacamentosChatbot) -> None:
    """Garante que responder 'Dealer DAF' apos um pedido de esclarecimento preserva marca=DAF e ano=2025."""
    turn1 = offline_bot.ask("Qual o volume de emplacamentos apenas da marca DAF em 2025 quebrado por Dealer")
    assert turn1.behavior == "esclarecer"
    assert "Dealer DAF" in turn1.answer_text

    turn2 = offline_bot.ask("Dealer DAF")
    assert turn2.behavior == "responder"
    assert turn2.spec is not None
    assert "dealer_daf" in turn2.spec.dimensions
    assert "marca=DAF" in turn2.answer_text
    assert "ano de 2025" in turn2.answer_text


def test_load_dotenv_file_reads_key_without_hardcoding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifica que load_dotenv_file carrega variaveis do arquivo .env de forma segura."""
    from emplacamentos_bot.config import load_dotenv_file

    fake_env = tmp_path / ".env"
    fake_env.write_text("ANTHROPIC_API_KEY=sk-ant-test-123\nLLM_PROVIDER=claude\n", encoding="utf-8")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)

    load_dotenv_file(env_path=fake_env, override=True)
    client = ClaudeLLMClient()
    assert client.api_key == "sk-ant-test-123"



