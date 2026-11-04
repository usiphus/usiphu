FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml README.md ./
COPY usiphu ./usiphu
COPY data ./data
COPY app ./app
COPY scripts ./scripts
RUN pip install --no-cache-dir . \
    && useradd --create-home --uid 10001 app \
    && mkdir -p /data /source-inbox /backups \
    && chown -R app:app /app /data /source-inbox /backups
USER app
EXPOSE 8501
VOLUME ["/data", "/source-inbox", "/backups"]
ENV USIPHU_DB_PATH=/data/usiphu.sqlite3
ENV USIPHU_SOURCE_DIR=/source-inbox
CMD ["streamlit", "run", "app/Home.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
