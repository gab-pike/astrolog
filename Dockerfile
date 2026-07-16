FROM python:3.12-slim

WORKDIR /app
COPY backend/requirements.txt .
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc g++ libc6-dev \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y gcc g++ libc6-dev \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

COPY backend/ ./backend/
COPY frontend/ ./frontend/

ENV DATA_DIR=/data \
    EPHE_PATH=/ephe \
    DEFAULT_LAT=43.55 \
    DEFAULT_LON=-96.73

EXPOSE 5000
WORKDIR /app/backend
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]
