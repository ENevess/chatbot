"""Utilitario de verificacao do banco SQLite populado."""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "emplacamentos_synthetic.db"


def verify_db(db_path: Path = DB_PATH) -> None:
    """Imprime um resumo das contagens, marcas, segmentos e armadilhas do banco."""
    with sqlite3.connect(db_path) as conn:
        print("=== 1. Volumes por Tabela ===")
        for table in [
            "chassi",
            "cidade",
            "cliente",
            "dealer_daf",
            "dealer_emplacamento",
            "emplacamento",
            "modelo",
            "cnae",
        ]:
            count = conn.execute(f"SELECT COUNT(*) FROM {table};").fetchone()[0]
            print(f"  {table:<22}: {count:>9,}")

        print("\n=== 2. Emplacamentos e Modelos por Fabricante (Marca) ===")
        rows = conn.execute(
            """
            SELECT
                m.fabricante,
                COUNT(DISTINCT m.id_modelo) AS qtd_modelos,
                COUNT(e.id_emplacamento) AS qtd_emplacamentos,
                ROUND(COUNT(e.id_emplacamento) * 100.0 / (SELECT COUNT(*) FROM emplacamento), 2) AS share_pct
            FROM modelo m
            LEFT JOIN chassi ch ON ch.id_modelo = m.id_modelo
            LEFT JOIN emplacamento e ON e.id_chassi = ch.id_chassi
            GROUP BY m.fabricante
            ORDER BY qtd_emplacamentos DESC;
            """
        ).fetchall()
        for fab, mod_cnt, emp_cnt, share in rows:
            print(f"  {fab:<16} | Modelos: {mod_cnt:>4} | Emplacamentos: {emp_cnt:>7,} ({share:>5.2f}%)")

        print("\n=== 3. Armadilhas Geograficas (Cidades) ===")
        traps = conn.execute(
            """
            SELECT id_cidade, nome_cidade, UF, codigo_cidade
            FROM cidade
            WHERE nome_cidade LIKE '%informado%'
               OR nome_cidade IN ('Mogi-Mirim', 'Embu', 'Parati', 'Presidente Juscelino')
            LIMIT 10;
            """
        ).fetchall()
        for cid, nome, uf, cod in traps:
            print(f"  id={cid} | nome='{nome}' | UF={uf} | IBGE={cod}")


if __name__ == "__main__":
    verify_db()
