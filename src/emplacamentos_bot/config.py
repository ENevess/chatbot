"""Carregador leve de variaveis de ambiente a partir do arquivo .env na raiz do projeto.

Cumpre as Secoes 4, 7 e 11 do AGENTS.md:
- Nenhum segredo fica hardcoded no codigo-fonte;
- O arquivo .env local e lido automaticamente (sem sobrescrever variaveis ja definidas no sistema)
  e permanece ignorado pelo .gitignore.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_ENV_PATH = ROOT_DIR / ".env"


def load_dotenv_file(env_path: Path = DEFAULT_ENV_PATH, override: bool = False) -> None:
    """Carrega pares CHAVE=VALOR do arquivo .env para os.environ."""
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and (override or key not in os.environ):
            os.environ[key] = value
