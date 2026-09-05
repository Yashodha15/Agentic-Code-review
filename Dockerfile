FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir ".[agents,api,console]"

RUN useradd --create-home --uid 10001 aegis && mkdir -p /data && chown aegis:aegis /data
USER aegis

ENV AEGIS_DATABASE_PATH=/data/aegis.db
CMD ["python", "-m", "aegis_review.cli", "api", "--host", "0.0.0.0"]
