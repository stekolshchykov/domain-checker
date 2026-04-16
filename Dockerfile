# syntax=docker/dockerfile:1
FROM mcr.microsoft.com/playwright/python:v1.58.0-noble

WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

# App code
COPY src/ ./src/
COPY tests/ ./tests/

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV APP_HOST=0.0.0.0
ENV APP_PORT=8000

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
