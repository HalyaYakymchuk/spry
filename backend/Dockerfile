# syntax=docker/dockerfile:1

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python -m venv /app/.venv \
    && . /app/.venv/bin/activate \
    && pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x ./scripts/entrypoint.sh

# --- dev target ---
FROM base AS dev
EXPOSE 8000
CMD ["./scripts/entrypoint.sh"]

# --- runtime target ---
FROM base AS lambda
ENTRYPOINT ["/app/.venv/bin/python", "-m", "awslambdaric"]
CMD ["app.lambda_handler.handler"]
