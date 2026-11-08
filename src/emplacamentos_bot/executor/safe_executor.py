"""Executor seguro de SQL com allowlist, read-only, limites e k-anonimato (Secao 7 do AGENTS.md)."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_DB_PATH = ROOT_DIR / "data" / "emplacamentos_synthetic.db"
DEFAULT_LOG_PATH = ROOT_DIR / "logs" / "audit.jsonl"

# Palavras-chave proibidas fora de SELECT puro
FORBIDDEN_SQL_KEYWORDS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "CREATE",
    "REPLACE",
    "TRUNCATE",
    "ATTACH",
    "DETACH",
    "PRAGMA",
    "VACUUM",
    "REINDEX",
    "ANALYZE",
}

# Colunas de identificacao individual (PII) que nunca podem aparecer em SELECT
FORBIDDEN_PII_COLUMNS = {
    "numero_documento",
    "razao_social",
    "nome_fantasia",
    "endereco",
    "complemento",
    "bairro",
    "email",
    "cep",
    "placa",
    "cnpj",
    "nome_socio",
    "nome_representante_legal",
}


class SecurityViolationError(PermissionError):
    """Excecao levantada quando uma consulta viola as regras de seguranca ou allowlist."""


class QueryExecutionLimitError(RuntimeError):
    """Excecao levantada quando a consulta excede tempo ou tamanho permitido."""


@dataclass
class ExecutorConfig:
    """Configuracao de seguranca e privacidade carregada do ambiente (Secao 7 e 11)."""

    db_path: Path = DEFAULT_DB_PATH
    log_path: Path = DEFAULT_LOG_PATH
    min_k_anonymity: int = 5
    max_rows: int = 1000
    timeout_seconds: float = 10.0
    max_result_bytes: int = 65536

    @classmethod
    def from_env(cls) -> ExecutorConfig:
        """Cria configuracao a partir de variaveis de ambiente."""
        from emplacamentos_bot.config import load_dotenv_file

        load_dotenv_file()
        db_env = os.getenv("DATABASE_PATH")
        log_env = os.getenv("LOG_FILE_PATH")
        return cls(
            db_path=Path(db_env) if db_env else DEFAULT_DB_PATH,
            log_path=Path(log_env) if log_env else DEFAULT_LOG_PATH,
            min_k_anonymity=int(os.getenv("MIN_K_ANONYMITY", "5")),
            max_rows=int(os.getenv("MAX_QUERY_ROWS", "1000")),
            timeout_seconds=float(os.getenv("QUERY_TIMEOUT_SECONDS", "10.0")),
            max_result_bytes=int(os.getenv("MAX_RESULT_BYTES", "65536")),
        )


@dataclass
class ExecutionResult:
    """Resultado seguro e agregado da execucao SQL."""

    rows: list[dict[str, Any]] = field(default_factory=list)
    privacy_suppressed: bool = False
    suppressed_count: int = 0
    truncated_by_row_limit: bool = False
    execution_time_ms: float = 0.0


class SafeSQLExecutor:
    """Executor deterministico e seguro para consultas agregadas no SQLite."""

    def __init__(
        self,
        allowed_tables: set[str],
        config: ExecutorConfig | None = None,
    ) -> None:
        self.allowed_tables = {t.lower() for t in allowed_tables}
        self.config = config or ExecutorConfig.from_env()

    def validate_sql(self, sql: str) -> None:
        """Valida que o SQL e estritamente SELECT e usa apenas tabelas da allowlist."""
        cleaned = sql.strip()
        if not cleaned:
            raise SecurityViolationError("Consulta SQL vazia não é permitida.")

        # Bloqueia comentarios SQL e multiplos statements
        if "--" in cleaned or "/*" in cleaned or "*/" in cleaned:
            raise SecurityViolationError("Comentários SQL não são permitidos.")

        statements = [s.strip() for s in cleaned.split(";") if s.strip()]
        if len(statements) > 1:
            raise SecurityViolationError("Múltiplos comandos SQL não são permitidos.")

        stmt = statements[0]
        upper_stmt = stmt.upper()

        # Deve comecar obrigatoriamente com SELECT ou WITH
        if not (upper_stmt.startswith("SELECT ") or upper_stmt.startswith("WITH ")):
            raise SecurityViolationError("Apenas consultas SELECT são permitidas.")

        # Remove literais entre aspas simples para inspecionar tokens com seguranca
        stmt_no_strings = re.sub(r"'[^']*'", "''", stmt)
        tokens = re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", stmt_no_strings)
        upper_tokens = {t.upper() for t in tokens}

        forbidden_found = upper_tokens.intersection(FORBIDDEN_SQL_KEYWORDS)
        if forbidden_found:
            raise SecurityViolationError(
                f"Comando SQL bloqueado por conter operação proibida: {', '.join(sorted(forbidden_found))}."
            )

        # Bloqueia colunas de identificacao individual (PII) e chassi.chassi (VIN individual)
        lower_tokens = {t.lower() for t in tokens}
        pii_found = lower_tokens.intersection(FORBIDDEN_PII_COLUMNS)
        if re.search(r"\b(?:ch|chassi)\.chassi\b", stmt_no_strings, flags=re.IGNORECASE):
            pii_found.add("chassi.chassi")
        if pii_found:
            raise SecurityViolationError(
                f"Acesso a colunas de identificação individual bloqueado: {', '.join(sorted(pii_found))}."
            )

        # Extrai nomes de CTEs (WITH nome_cte AS (...)) para nao confundi-las com tabelas fisicas
        cte_names = {
            m.lower()
            for m in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s+AS\s*\(", stmt_no_strings, flags=re.IGNORECASE)
        }

        # Extrai tabelas referenciadas em FROM e JOIN
        referenced_tables = {
            m.lower()
            for m in re.findall(r"\b(?:FROM|JOIN)\s+([A-Za-z_][A-Za-z0-9_]*)\b", stmt_no_strings, flags=re.IGNORECASE)
        }

        physical_tables = referenced_tables - cte_names
        if not physical_tables:
            raise SecurityViolationError("A consulta deve referenciar pelo menos uma tabela da allowlist.")

        unauthorized_tables = physical_tables - self.allowed_tables
        if unauthorized_tables:
            raise SecurityViolationError(
                f"Tabela(s) fora da allowlist bloqueada(s): {', '.join(sorted(unauthorized_tables))}."
            )

    def execute(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
        question: str = "",
        spec_dict: dict[str, Any] | None = None,
    ) -> ExecutionResult:
        """Valida, executa em modo read-only, aplica k-anonimato e registra auditoria."""
        t0 = time.perf_counter()
        params = params or {}

        try:
            self.validate_sql(sql)

            db_uri = f"file:{self.config.db_path.resolve().as_posix()}?mode=ro"
            conn = sqlite3.connect(db_uri, uri=True, timeout=self.config.timeout_seconds)
            try:
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA query_only = ON;")

                deadline = time.perf_counter() + self.config.timeout_seconds

                def _progress_handler() -> int:
                    if time.perf_counter() > deadline:
                        return 1  # Aborta execucao no SQLite
                    return 0

                conn.set_progress_handler(_progress_handler, 10_000)

                cursor = conn.execute(sql, params)
                raw_rows = cursor.fetchmany(self.config.max_rows + 1)
            except sqlite3.OperationalError as exc:
                if "interrupted" in str(exc).lower():
                    raise QueryExecutionLimitError(
                        f"A consulta excedeu o tempo limite de {self.config.timeout_seconds}s."
                    ) from exc
                raise
            finally:
                conn.close()

            truncated = len(raw_rows) > self.config.max_rows
            if truncated:
                raw_rows = raw_rows[: self.config.max_rows]

            dict_rows = [dict(r) for r in raw_rows]

            # Verifica limite de bytes do resultado
            serialized_bytes = len(json.dumps(dict_rows, ensure_ascii=False).encode("utf-8"))
            if serialized_bytes > self.config.max_result_bytes:
                raise QueryExecutionLimitError(
                    f"O tamanho do resultado ({serialized_bytes} bytes) excede o limite de "
                    f"{self.config.max_result_bytes} bytes."
                )

            # Aplica regra de contagem minima (k-anonimato)
            processed_rows, suppressed_flag, suppressed_cnt = self._apply_k_anonymity(dict_rows)
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)

            result = ExecutionResult(
                rows=processed_rows,
                privacy_suppressed=suppressed_flag,
                suppressed_count=suppressed_cnt,
                truncated_by_row_limit=truncated,
                execution_time_ms=elapsed_ms,
            )

            self.log_audit(
                question=question,
                spec_dict=spec_dict,
                sql=sql,
                status="success_suppressed" if suppressed_flag else "success",
                row_count=len(processed_rows),
                execution_time_ms=elapsed_ms,
            )
            return result

        except Exception as exc:
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            self.log_audit(
                question=question,
                spec_dict=spec_dict,
                sql=sql,
                status=f"error:{type(exc).__name__}",
                error_message=str(exc),
                execution_time_ms=elapsed_ms,
            )
            raise

    def _apply_k_anonymity(
        self,
        rows: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], bool, int]:
        """Suprime valores quando a contagem subjacente (_row_count) e menor que k."""
        k = self.config.min_k_anonymity
        safe_rows: list[dict[str, Any]] = []
        suppressed_count = 0

        for row in rows:
            row_copy = dict(row)
            underlying_count = row_copy.pop("_row_count", None)

            if underlying_count is not None and int(underlying_count) < k:
                suppressed_count += 1
                for key in list(row_copy.keys()):
                    if key in ("valor", "volume", "volume_atual", "volume_anterior", "variacao_absoluta"):
                        row_copy[key] = None
                row_copy["suprimido_privacidade"] = True
            else:
                row_copy["suprimido_privacidade"] = False

            safe_rows.append(row_copy)

        return safe_rows, (suppressed_count > 0), suppressed_count

    def log_audit(
        self,
        question: str,
        spec_dict: dict[str, Any] | None,
        sql: str,
        status: str,
        row_count: int = 0,
        error_message: str | None = None,
        execution_time_ms: float = 0.0,
    ) -> None:
        """Registra log estruturado em JSONL sem dados pessoais nem chaves de API."""
        self.config.log_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "question": question,
            "specification": spec_dict or {},
            "sql": sql,
            "status": status,
            "result_row_count": row_count,
            "execution_time_ms": execution_time_ms,
        }
        if error_message:
            entry["error"] = error_message

        with self.config.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
