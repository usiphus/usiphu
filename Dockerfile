FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    USIPHU_DB_PATH=/var/lib/usiphu/usiphu_data.sqlite3 \
    USIPHU_SOURCE_DIR=/var/lib/usiphu/source_inbox \
    USIPHU_BACKUP_DIR=/var/lib/usiphu/backups

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 usiphu \
    && useradd --system --uid 10001 --gid usiphu --home-dir /app usiphu

COPY pyproject.toml README.md ./
COPY usiphu ./usiphu
COPY app ./app
COPY data ./data
COPY scripts ./scripts

RUN pip install --upgrade pip \
    && pip install . \
    && mkdir -p /var/lib/usiphu/source_inbox /var/lib/usiphu/backups \
    && chown -R usiphu:usiphu /app /var/lib/usiphu

USER usiphu
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=3)"
CMD ["streamlit", "run", "app/Home.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
