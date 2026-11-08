"""Testes unitarios e de integracao para a interface CLI (Tarefa 6 - Secao 8 e 10)."""

from pathlib import Path

import pytest

from emplacamentos_bot.interfaces.cli import run_cli

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = ROOT_DIR / "data" / "emplacamentos_synthetic.db"


@pytest.mark.skipif(not DB_PATH.exists(), reason="Banco sintetico local nao encontrado")
def test_cli_single_question_section8_format(capsys: pytest.CaptureFixture[str]) -> None:
    """Pronto quando (Secao 10, Tarefa 6): da para perguntar na CLI e receber resposta no formato da Secao 8."""
    exit_code = run_cli(
        [
            "--provider",
            "mock",
            "--show-sql",
            "Qual a participação de mercado da DAF em 2025?",
        ]
    )
    assert exit_code == 0
    captured = capsys.readouterr().out
    assert "1. **Resposta direta:**" in captured
    assert "DAF:" in captured
    assert "2. **Período e filtros aplicados:**" in captured
    assert "3. **Definição da métrica" in captured
    assert "4. **Privacidade:**" in captured
    assert "[SQL Determinístico Gerado]:" in captured


def test_cli_interactive_repl_mode(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Testa o modo interativo da CLI enviando uma pergunta sem periodo e depois 'sair'."""
    inputs = iter(["Quantos caminhões foram emplacados?", "sair"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    exit_code = run_cli(["--provider", "mock"])
    assert exit_code == 0
    captured = capsys.readouterr().out
    assert "Esclarecimento necessário:" in captured
    assert "Encerrando o Chatbot." in captured
