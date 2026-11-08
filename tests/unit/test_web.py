"""Testes unitarios e de integracao para a Interface Web (Tarefa 8 - Secao 5 e 10)."""

from http import HTTPStatus
from pathlib import Path

import pytest

from emplacamentos_bot.interfaces.web import MOBILE_FIRST_HTML, handle_api_ask

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
    assert "11,62%" in resp["answer_text"]
    assert resp["sql"] is not None
    assert len(resp["rows"]) == 1
