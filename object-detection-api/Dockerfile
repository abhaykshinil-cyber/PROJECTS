# ---- Stage 1: base image ----
FROM python:3.11-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ---- Stage 2: dependencies ----
FROM base AS deps

COPY requirements.txt .

RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# ---- Stage 3: pre-download all YOLOv8 weights directly into /app/models ----
FROM deps AS model-download

ENV YOLO_CONFIG_DIR=/app/models

COPY scripts/download_models.py /tmp/download_models.py
RUN mkdir -p /app/models && python /tmp/download_models.py

# ---- Stage 4: runtime ----
FROM model-download AS runtime

COPY app/ ./app/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    YOLO_CONFIG_DIR=/app/models \
    DEFAULT_MODEL=yolov8n

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
