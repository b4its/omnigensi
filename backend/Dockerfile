FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System dependencies (runtime + build tools for wheels that need compiling)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies (separate layer for better cache)
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Application source
COPY . /app/

# Drop host-only artifacts and make sure the workspace dir exists
RUN rm -rf /app/.venv /app/.pytest_cache /app/workspace \
    && find /app -type d -name __pycache__ -prune -exec rm -rf {} + \
    && mkdir -p /app/workspace

# ---------------------------------------------------------------------------
# development: hot-reload enabled, runs as root so the bind-mounted
#              workspace stays writable from the host
# ---------------------------------------------------------------------------
FROM base AS development

ENV APP_ENV=development

EXPOSE 8123

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
    CMD curl -fsS http://127.0.0.1:8123/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8123", "--reload"]

# ---------------------------------------------------------------------------
# production: non-root user, multiple workers, no reload
# ---------------------------------------------------------------------------
FROM base AS production

RUN groupadd --system --gid 1001 appuser \
    && useradd --system --uid 1001 --gid appuser --create-home appuser \
    && chown -R appuser:appuser /app

USER appuser

ENV APP_ENV=production

EXPOSE 8123

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8123/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8123", "--workers", "2"]
