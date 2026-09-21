# Backend API: FastAPI service + the onboarding-agent/onboarding-core workspace libraries. Creates tables and seeds the catalog on start (idempotent).
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app
# Third-party dependencies first (cached layer): the lock needs the workspace members' pyproject files.
COPY pyproject.toml uv.lock .python-version ./
COPY packages/core/pyproject.toml packages/core/
COPY packages/agent/pyproject.toml packages/agent/
RUN uv sync --frozen --no-dev --no-install-project --no-install-workspace

# Then the workspace libraries (onboarding-core, onboarding-agent) and the API service itself.
COPY packages ./packages
RUN uv sync --frozen --no-dev --no-install-project --no-editable
COPY app ./app

RUN useradd --system --uid 10001 --no-create-home appuser \
    && mkdir -p /var/lib/agent-config && chown appuser /var/lib/agent-config
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*", "--timeout-graceful-shutdown", "5"]
