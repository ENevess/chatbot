FROM python:3.12-slim

WORKDIR /app

# Copia os arquivos de definicao e codigo-fonte (nunca copia bancos locais ou .env)
COPY pyproject.toml AGENTS.md ./
COPY semantic ./semantic
COPY scripts ./scripts
COPY src ./src

# Instala o pacote sem dependencias pesadas
RUN pip install --no-cache-dir -e .

# Variaveis padrao para execucao em nuvem (Render / Docker)
ENV HOST=0.0.0.0
ENV PORT=8000
ENV LLM_PROVIDER=claude
ENV LLM_MODEL=claude-haiku-5-5
ENV SYNTHETIC_DB_SCALE=1.0

EXPOSE 8000

CMD ["python", "-m", "emplacamentos_bot.interfaces.web"]
