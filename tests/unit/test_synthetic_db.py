"""Testes unitarios para a inicializacao do schema e o gerador de dados sinteticos."""

import sqlite3
from pathlib import Path

from scripts.generate_synthetic_db import BRANDS_CONFIG, TARGET_COUNTS, populate_database


def test_populate_database_small_scale(tmp_path: Path) -> None:
    """Valida que o gerador cria todas as tabelas, respeita as 7 marcas e injeta as armadilhas."""
    test_db = tmp_path / "test_synthetic.db"
    counts = populate_database(db_path=test_db, scale=0.01, seed=42)

    assert counts["modelo"] == TARGET_COUNTS["modelo"]
    assert counts["cidade"] == TARGET_COUNTS["cidade"]
    assert counts["dealer_daf"] == TARGET_COUNTS["dealer_daf"]
    assert counts["dealer_emplacamento"] == TARGET_COUNTS["dealer_emplacamento"]
    assert counts["cliente"] > 0
    assert counts["chassi"] > 0
    assert counts["emplacamento"] > 0

    with sqlite3.connect(test_db) as conn:
        # 1. Verifica que exatamente as 7 marcas solicitadas estao presentes em modelo.fabricante
        brands = {row[0] for row in conn.execute("SELECT DISTINCT fabricante FROM modelo;").fetchall()}
        expected_brands = {
            "AGRALE",
            "DAF",
            "IVECO",
            "SCANIA",
            "MERCEDEZ-BENZ",
            "VOLVO",
            "VOLKSWAGEN",
        }
        assert brands == expected_brands
        assert brands == set(BRANDS_CONFIG.keys())

        # 2. Verifica armadilha de cidade "Não informado"
        nao_informado = conn.execute(
            "SELECT COUNT(*) FROM cidade WHERE nome_cidade = 'Não informado';"
        ).fetchone()[0]
        assert nao_informado >= 1

        # 3. Verifica que municipio de emplacamento e municipio de cliente podem divergir
        divergent_cities = conn.execute(
            """
            SELECT COUNT(*)
            FROM emplacamento e
            JOIN cliente c ON e.id_cliente = c.id_cliente
            WHERE e.id_cidade != c.id_cidade;
            """
        ).fetchone()[0]
        assert divergent_cities > 0
