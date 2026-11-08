"""Testes unitarios da Camada Semantica v0 e do Compilador Deterministico SQL (Tarefa 3)."""

import sqlite3
from pathlib import Path

import pytest

from emplacamentos_bot.compiler.sql_compiler import (
    AmbiguousQueryError,
    FilterSpec,
    PeriodSpec,
    QuerySpec,
    SemanticValidationError,
    SQLCompiler,
)
from emplacamentos_bot.semantic.loader import load_semantic_catalog

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = ROOT_DIR / "data" / "emplacamentos_synthetic.db"


def test_load_semantic_catalog() -> None:
    """Valida que semantic/emplacamentos.yaml carrega com todas as 5 metricas e regras."""
    catalog = load_semantic_catalog()
    assert catalog.version == "0.1.1"
    assert catalog.governance.min_k_anonymity == 5
    assert catalog.governance.require_explicit_period is True
    assert set(catalog.metrics.keys()) == {
        "volume_emplacamentos",
        "participacao_mercado_marca",
        "participacao_segmento",
        "ranking_modelos",
        "variacao_periodos",
    }
    # Garante que quadros sensiveis (quadro_societario, cnpj_cnae) nao estao na allowlist
    allowed_tables = catalog.get_allowed_tables()
    assert "quadro_societario" not in allowed_tables
    assert "cnpj_cnae" not in allowed_tables


def test_compiler_rejects_missing_period() -> None:
    """Valida a regra inegociavel #2: sem periodo informado, levanta AmbiguousQueryError."""
    catalog = load_semantic_catalog()
    compiler = SQLCompiler(catalog, reference_date="2026-11-08")

    spec = QuerySpec(metric="volume_emplacamentos", period=None)
    with pytest.raises(AmbiguousQueryError, match="período"):
        compiler.compile(spec)


def test_compiler_rejects_unknown_metric() -> None:
    """Valida que metricas inexistentes na camada semantica sao recusadas."""
    catalog = load_semantic_catalog()
    compiler = SQLCompiler(catalog)

    spec = QuerySpec(
        metric="lucro_liquido_concessionaria",
        period=PeriodSpec(kind="year", value="2025"),
    )
    with pytest.raises(SemanticValidationError, match="não existe na camada semântica"):
        compiler.compile(spec)


@pytest.mark.skipif(not DB_PATH.exists(), reason="Banco sintetico local nao encontrado")
def test_all_five_initial_metrics_compile_and_run() -> None:
    """Pronto quando (Secao 10, Tarefa 3): cada metrica inicial compilar e rodar no SQLite."""
    catalog = load_semantic_catalog()
    compiler = SQLCompiler(catalog, reference_date="2026-11-08")

    specs = [
        # 1. Volume no ultimo mes fechado (2026-10)
        QuerySpec(
            metric="volume_emplacamentos",
            period=PeriodSpec(kind="last_closed_month"),
        ),
        # 2. Volume por regiao (incluindo a 6a regiao 'Não informado')
        QuerySpec(
            metric="volume_emplacamentos",
            dimensions=["regiao_emplacamento"],
            period=PeriodSpec(kind="year", value="2025"),
        ),
        # 3. Participacao de mercado por marca
        QuerySpec(
            metric="participacao_mercado_marca",
            period=PeriodSpec(kind="year", value="2025"),
            filters=[FilterSpec(dimension="marca", operator="=", value="DAF")],
        ),
        # 4. Participacao por segmento
        QuerySpec(
            metric="participacao_segmento",
            period=PeriodSpec(kind="year", value="2025"),
        ),
        # 5. Ranking de modelos
        QuerySpec(
            metric="ranking_modelos",
            period=PeriodSpec(kind="year", value="2025"),
            limit=5,
        ),
        # 6. Variacao entre periodos (2025 vs 2024)
        QuerySpec(
            metric="variacao_periodos",
            period=PeriodSpec(kind="year", value="2025", comparison_value="2024"),
        ),
    ]

    with sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True) as conn:
        for spec in specs:
            compiled = compiler.compile(spec)
            assert compiled.sql.upper().startswith(("SELECT", "WITH"))
            rows = conn.execute(compiled.sql, compiled.params).fetchall()
            assert len(rows) > 0
