"""Script utilitario para criar/recriar a estrutura DDL do banco SQLite local."""

import sqlite3
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SCHEMA_PATH = ROOT_DIR / "scripts" / "schema.sql"
DEFAULT_DB_PATH = ROOT_DIR / "data" / "emplacamentos_synthetic.db"


def init_database(
    db_path: Path = DEFAULT_DB_PATH,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
) -> list[str]:
    """Cria ou recria o banco SQLite a partir do arquivo DDL e retorna as tabelas criadas."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    sql_script = schema_path.read_text(encoding="utf-8")

    with sqlite3.connect(db_path) as conn:
        conn.executescript(sql_script)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name;"
        )
        tables = [row[0] for row in cursor.fetchall()]

    return tables


if __name__ == "__main__":
    created_tables = init_database()
    print(f"Banco SQLite inicializado em: {DEFAULT_DB_PATH}")
    print(f"Tabelas criadas ({len(created_tables)}): {', '.join(created_tables)}")
