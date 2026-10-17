# The Qapital API as one container, listening on port 7860 (in production behind Caddy: deploy/oracle).
#   docker build -t qapital-api .
#   docker run -p 7860:7860 -e QAPITAL_SNAPSHOT_REPO=<owner>/<repo> -e QAPITAL_CORS_ORIGINS=http://localhost:5173 qapital-api
# Prices are not in the image: at start-up the API downloads the newest snapshot from the repo's "data" release
# (QAPITAL_SNAPSHOT_REPO) and checks for a newer one every few hours. Results go to DATABASE_URL (Postgres in
# production; a SQLite file inside the container otherwise, which a restart wipes).
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /usr/local/bin/uv
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --extra api
COPY src ./src
RUN uv sync --locked --extra api

COPY data/universes ./data/universes
COPY data/costs ./data/costs
RUN useradd --create-home --uid 1000 app && mkdir -p /app/data/snapshots && chown -R app /app/data
USER app

ENV PATH="/app/.venv/bin:$PATH" \
    QAPITAL_DATA=/app/data \
    QAPITAL_TRUST_PROXY=1 \
    QAPITAL_WORKERS=2
EXPOSE 7860
HEALTHCHECK --interval=60s --timeout=5s --start-period=180s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7860/health')"
CMD ["uvicorn", "qapital.api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "7860"]
