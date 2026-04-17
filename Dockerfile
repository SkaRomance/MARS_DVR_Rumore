FROM python:3.14-slim AS builder
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.14-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local
COPY src/ src/
COPY static/ static/
COPY migrations/ migrations/
COPY alembic.ini alembic.ini
COPY docker/docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
EXPOSE 8085

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "src.bootstrap.main:app", "--host", "0.0.0.0", "--port", "8085"]