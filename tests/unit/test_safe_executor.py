"""Testes unitarios para o Executor Seguro (Tarefa 4 - Secao 7 e 10 do AGENTS.md)."""

import json
from pathlib import Path

import pytest

from emplacamentos_bot.executor.safe_executor import (
    ExecutorConfig,
    QueryExecutionLimitError,
    SafeSQLExecutor,
    SecurityViolationError,
)
from emplacamentos_bot.semantic.loader import load_semantic_catalog

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = ROOT_DIR / "data" / "emplacamentos_synthetic.db"


@pytest.fixture
def safe_executor(tmp_path: Path) -> SafeSQLExecutor:
    """Cria uma instancia de SafeSQLExecutor com log isolado em tmp_path."""
    catalog = load_semantic_catalog()
    config = ExecutorConfig(
        db_path=DB_PATH,
        log_path=tmp_path / "test_audit.jsonl",
        min_k_anonymity=5,
        max_rows=100,
        timeout_seconds=5.0,
        max_result_bytes=65536,
    )
    return SafeSQLExecutor(allowed_tables=catalog.get_allowed_tables(), config=config)


def test_blocks_non_select_commands(safe_executor: SafeSQLExecutor) -> None:
    """Bloqueia comandos de escrita/DDL como DELETE, DROP, UPDATE, INSERT, PRAGMA."""
    malicious_queries = [
        "DELETE FROM emplacamento WHERE id_emplacamento = 1",
        "DROP TABLE emplacamento",
        "UPDATE modelo SET fabricante = 'HACK'",
        "INSERT INTO cnae VALUES (999, 'Teste')",
        "PRAGMA table_info(cliente)",
        "SELECT COUNT(*) FROM emplacamento; DROP TABLE chassi",
        "SELECT COUNT(*) FROM emplacamento -- comentario suspeito",
    ]
    for sql in malicious_queries:
        with pytest.raises(SecurityViolationError):
            safe_executor.validate_sql(sql)


def test_blocks_unauthorized_tables(safe_executor: SafeSQLExecutor) -> None:
    """Pronto quando (Secao 10, Tarefa 4): consultas fora da allowlist sao bloqueadas."""
    unauthorized_queries = [
        "SELECT COUNT(*) FROM quadro_societario",
        "SELECT COUNT(*) FROM cnpj_cnae",
        "SELECT name FROM sqlite_master WHERE type='table'",
        "SELECT COUNT(*) FROM emplacamento e JOIN quadro_societario qs ON 1=1",
    ]
    for sql in unauthorized_queries:
        with pytest.raises(SecurityViolationError, match="allowlist"):
            safe_executor.validate_sql(sql)


def test_blocks_pii_columns(safe_executor: SafeSQLExecutor) -> None:
    """Bloqueia qualquer tentativa de projetar ou filtrar colunas de PII (CPF/CNPJ, razao_social, placa, email)."""
    pii_queries = [
        "SELECT razao_social, COUNT(*) FROM cliente GROUP BY razao_social",
        "SELECT email FROM cliente LIMIT 5",
        "SELECT placa FROM emplacamento LIMIT 5",
        "SELECT numero_documento FROM cliente LIMIT 5",
    ]
    for sql in pii_queries:
        with pytest.raises(SecurityViolationError, match="identificação individual"):
            safe_executor.validate_sql(sql)


@pytest.mark.skipif(not DB_PATH.exists(), reason="Banco sintetico local nao encontrado")
def test_enforces_k_anonymity_suppression(safe_executor: SafeSQLExecutor) -> None:
    """Verifica que resultados com _row_count < 5 sao suprimidos por privacidade."""
    # O modelo id_modelo = 1155 tem 6 emplacamentos totais, sendo 3 no ano de 2020 (< 5)
    sql = """
    SELECT m.modelo AS modelo,
           COUNT(e.id_emplacamento) AS valor,
           COUNT(e.id_emplacamento) AS _row_count
    FROM emplacamento e
    INNER JOIN chassi ch ON e.id_chassi = ch.id_chassi
    INNER JOIN modelo m ON ch.id_modelo = m.id_modelo
    WHERE m.id_modelo = :mid
      AND strftime('%Y', e.data_emplacamento) = '2020'
    GROUP BY m.modelo
    """
    result = safe_executor.execute(
        sql=sql,
        params={"mid": 1155},
        question="Teste k-anonimato modelo raro",
        spec_dict={"metric": "volume_emplacamentos"},
    )
    assert result.privacy_suppressed is True
    assert result.suppressed_count == 1
    assert result.rows[0]["valor"] is None
    assert result.rows[0]["suprimido_privacidade"] is True

    # Verifica se o log de auditoria foi gravado corretamente sem dados sensiveis
    log_lines = safe_executor.config.log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(log_lines) == 1
    log_entry = json.loads(log_lines[0])
    assert log_entry["status"] == "success_suppressed"
    assert log_entry["question"] == "Teste k-anonimato modelo raro"


@pytest.mark.skipif(not DB_PATH.exists(), reason="Banco sintetico local nao encontrado")
def test_enforces_max_rows_and_result_bytes(tmp_path: Path) -> None:
    """Verifica truncamento por limite de linhas e bloqueio por limite de bytes."""
    catalog = load_semantic_catalog()
    small_config = ExecutorConfig(
        db_path=DB_PATH,
        log_path=tmp_path / "limit_audit.jsonl",
        min_k_anonymity=5,
        max_rows=5,
        timeout_seconds=5.0,
        max_result_bytes=65536,
    )
    executor = SafeSQLExecutor(allowed_tables=catalog.get_allowed_tables(), config=small_config)

    sql = """
    SELECT m.fabricante AS marca,
           COUNT(e.id_emplacamento) AS valor,
           COUNT(e.id_emplacamento) AS _row_count
    FROM emplacamento e
    INNER JOIN chassi ch ON e.id_chassi = ch.id_chassi
    INNER JOIN modelo m ON ch.id_modelo = m.id_modelo
    GROUP BY m.fabricante
    """
    res = executor.execute(sql)
    # Existem 7 marcas, mas max_rows=5 trunca em 5
    assert len(res.rows) == 5
    assert res.truncated_by_row_limit is True

    # Testa limite estrito de bytes
    tiny_byte_config = ExecutorConfig(
        db_path=DB_PATH,
        log_path=tmp_path / "byte_audit.jsonl",
        min_k_anonymity=5,
        max_rows=100,
        timeout_seconds=5.0,
        max_result_bytes=10,  # 10 bytes apenas -> deve falhar
    )
    tiny_executor = SafeSQLExecutor(allowed_tables=catalog.get_allowed_tables(), config=tiny_byte_config)
    with pytest.raises(QueryExecutionLimitError, match="tamanho do resultado"):
        tiny_executor.execute(sql)
