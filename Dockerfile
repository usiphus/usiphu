FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml README.md ./
COPY usiphu ./usiphu
COPY data ./data
COPY app ./app
RUN pip install --no-cache-dir .
EXPOSE 8501
VOLUME ["/data"]
ENV USIPHU_DB_PATH=/data/usiphu.sqlite3
CMD ["streamlit", "run", "app/Home.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
