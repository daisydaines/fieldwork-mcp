# Hosted Fieldwork MCP: site + /connect + /mcp
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FIELDWORK_MCP_TRANSPORT=streamable-http \
    FIELDWORK_MCP_HOSTED=1 \
    FIELDWORK_MCP_HOST=0.0.0.0 \
    FIELDWORK_MCP_PORT=8000 \
    FIELDWORK_MCP_ALLOW_ENV_FALLBACK=0 \
    FIELDWORK_LANDING_DIR=/app/landing \
    FIELDWORK_VAULT_DB=/data/vault.sqlite3

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY landing ./landing

RUN pip install --no-cache-dir -e . \
    && mkdir -p /data

EXPOSE 8000

# Require FIELDWORK_VAULT_SECRET (+ optional FIELDWORK_PUBLIC_BASE_URL) at runtime.
CMD ["fieldwork-mcp"]
