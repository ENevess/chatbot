"""Testes unitarios e de integracao para a Interface Web (Tarefa 8 - Secao 5 e 10)."""

from http import HTTPStatus
from pathlib import Path

import pytest

from emplacamentos_bot.executor.safe_executor import ExecutorConfig, SafeSQLExecutor
from emplacamentos_bot.interfaces.architecture_page import ARCHITECTURE_HTML
from emplacamentos_bot.interfaces.logs_page import LOGS_VIEWER_HTML
from emplacamentos_bot.interfaces.web import MOBILE_FIRST_HTML, handle_api_ask, handle_api_feedback
from emplacamentos_bot.semantic.loader import load_semantic_catalog

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = ROOT_DIR / "data" / "emplacamentos_synthetic.db"


def test_mobile_first_html_has_responsive_viewport_and_controls() -> None:
    """Verifica que o HTML possui meta viewport mobile-first, disclaimer de dados sinteticos e 2 blocos de chips."""
    assert 'name="viewport"' in MOBILE_FIRST_HTML
    assert "width=device-width" in MOBILE_FIRST_HTML
    assert "/api/ask" in MOBILE_FIRST_HTML
    assert "AVISO DE DADOS SINTÉTICOS" in MOBILE_FIRST_HTML
    assert "100% sintéticos" in MOBILE_FIRST_HTML
    assert MOBILE_FIRST_HTML.count('class="chips-row"') == 2
    assert "/arquitetura.html" in MOBILE_FIRST_HTML


def test_architecture_html_contains_poc_sections() -> None:
    """Verifica que a pagina /arquitetura.html documenta o pipeline, isolamento da LLM e camada semantica."""
    assert "Arquitetura da PoC" in ARCHITECTURE_HTML
    assert "Claude Haiku 5.5" in ARCHITECTURE_HTML
    assert "777.365" in ARCHITECTURE_HTML
    assert "k-anonimato" in ARCHITECTURE_HTML



def test_api_ask_rejects_empty_question() -> None:
    """Verifica que perguntas vazias retornam HTTP 400."""
    status, resp = handle_api_ask({"question": "   "})
    assert status == HTTPStatus.BAD_REQUEST
    assert "obrigatório" in resp["error"]


@pytest.mark.skipif(not DB_PATH.exists(), reason="Banco sintetico local nao encontrado")
def test_api_ask_returns_formatted_answer_and_sql() -> None:
    """Verifica que /api/ask executa o pipeline completo e retorna os dados esperados."""
    status, resp = handle_api_ask(
        {
            "question": "Qual a participação de mercado da DAF em 2026 apenas no segmento pesado?",
            "provider": "mock",
        }
    )
    assert status == HTTPStatus.OK
    assert resp["behavior"] == "responder"
    assert resp["interaction_id"]
    assert "11,62%" in resp["answer_text"]
    assert resp["sql"] is not None
    assert len(resp["rows"]) == 1


def test_feedback_logging_and_consolidation(tmp_path: Path) -> None:
    """Verifica que a avaliacao positiva/negativa e gravada no log e consolidada em read_logs()."""
    catalog = load_semantic_catalog()
    cfg = ExecutorConfig(db_path=DB_PATH, log_path=tmp_path / "feedback_audit.jsonl")
    executor = SafeSQLExecutor(allowed_tables=catalog.get_allowed_tables(), config=cfg)

    turn_id = executor.log_audit(
        question="Pergunta de teste para feedback",
        spec_dict={"metric": "volume_emplacamentos"},
        sql="SELECT COUNT(id_emplacamento) FROM emplacamento",
        status="success",
        row_count=1,
    )

    status, resp = handle_api_feedback(
        {
            "interaction_id": turn_id,
            "rating": "negative",
            "comment": "Filtrou o período errado",
            "question": "Pergunta de teste para feedback",
        },
        executor=executor,
    )
    assert status == HTTPStatus.OK
    assert resp["rating"] == "negative"

    logs = executor.read_logs()
    query_entries = [e for e in logs if e.get("event_type") == "query"]
    assert len(query_entries) == 1
    assert query_entries[0]["feedback"]["rating"] == "negative"
    assert query_entries[0]["feedback"]["comment"] == "Filtrou o período errado"
    assert "/api/logs/download" in LOGS_VIEWER_HTML

