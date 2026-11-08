"""Testes unitarios e de integracao para o Runner de Avaliacao (Tarefa 7 - Secao 9 e 10)."""

from pathlib import Path

import pytest

from emplacamentos_bot.evaluation.runner import (
    format_evaluation_report,
    load_reference_questions,
    run_evaluation,
)

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = ROOT_DIR / "data" / "emplacamentos_synthetic.db"


def test_load_reference_questions_has_at_least_10_items() -> None:
    """Garante que tests/reference_questions.yaml possui ao menos 10 perguntas validas."""
    questions = load_reference_questions()
    assert len(questions) >= 10


@pytest.mark.skipif(not DB_PATH.exists(), reason="Banco sintetico local nao encontrado")
def test_evaluation_runner_meets_v0_targets() -> None:
    """Pronto quando (Secao 10, Tarefa 7): o relatorio mostrar os tres indicadores e atingir as metas."""
    summary = run_evaluation()
    report_text = format_evaluation_report(summary)

    assert "1. Acerto (respondeu e acertou)" in report_text
    assert "2. Recusa ou esclarecimento correto" in report_text
    assert "3. Erro confiante" in report_text

    # Metas da Secao 9: >= 90% geral, 100% nas centrais, 0 erro confiante nas centrais
    assert summary.erros_confiantes == 0
    assert summary.erros_confiantes_centrais == 0
    assert summary.central_accuracy_pct == 100.0
    assert summary.overall_accuracy_pct >= 90.0
    assert summary.passes_v0_gate is True
