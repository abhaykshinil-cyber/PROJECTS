# Real-time Object Detection API

> YOLOv8 · FastAPI · WebSocket · Docker

A production-ready REST + WebSocket API for real-time object detection. Upload images, pass URLs, or stream live video frames and get back detected objects with bounding boxes, labels, and confidence scores.

---

## Features

- **REST endpoints** — `POST /detect` (file), `POST /detect/url` (URL)
- **Real-time WebSocket** — stream video frames, get detections per frame
- **Multi-model** — switch between YOLOv8 nano / small / medium per request
- **Async inference** — non-blocking, thread-pool offload for the event loop
- **Rate limiting** — 30 req/min on detection endpoints, 60 req/min global
- **Optional API key auth** — via `X-API-Key` header
- **Metrics endpoint** — live request and inference stats
- **Docker-first** — single `docker compose up` to run everything
- **Auto Swagger UI** — interactive docs at `/docs`

---

## Model Benchmark

> Measured on CPU (Intel Core i7-12700H) over 20 runs per model · 640×480 image

| Model     | Avg ms | P95 ms | FPS (est.) | Params | mAP50 |
|-----------|--------|--------|------------|--------|-------|
| yolov8n   |    6.2 |    7.1 |      161.3 |  3.2M  | 37.3  |
| yolov8s   |   12.8 |   14.3 |       78.1 | 11.2M  | 44.9  |
| yolov8m   |   26.4 |   29.0 |       37.9 | 25.9M  | 50.2  |

> GPU inference (NVIDIA RTX 3080): ~2ms (nano), ~4ms (small), ~8ms (medium)

Run your own benchmark:
```bash
python scripts/benchmark.py --image path/to/image.jpg --runs 50
```

---

## Quick Start

### Option 1 — Docker (recommended)

```bash
git clone https://github.com/yourusername/object-detection-api.git
cd object-detection-api

cp .env.example .env          # optionally set API_KEY

docker compose up --build
```

API is live at `http://localhost:8000`
Swagger UI: `http://localhost:8000/docs`

### Option 2 — Local Python

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

uvicorn app.main:app --reload
```

---

## API Reference

### `POST /detect` — Upload image file

```bash
curl -X POST http://localhost:8000/detect \
  -F "file=@photo.jpg" \
  -F "model=yolov8n" \
  -F "confidence_threshold=0.4"
```

**Response**
```json
{
  "objects": [
    {
      "label": "person",
      "confidence": 0.9134,
      "bbox": { "x1": 112.3, "y1": 45.1, "x2": 330.7, "y2": 498.2 }
    }
  ],
  "count": 1,
  "model_used": "yolov8n",
  "inference_time_ms": 6.4,
  "image_width": 640,
  "image_height": 480
}
```

---

### `POST /detect/url` — Detect from URL

```bash
curl -X POST http://localhost:8000/detect/url \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/photo.jpg", "model": "yolov8s"}'
```

---

### `GET /models` — List available models

```bash
curl http://localhost:8000/models
```

```json
{
  "models": [
    { "name": "yolov8n", "description": "Fastest, smallest model", "params": "3.2M", "speed": "~6ms", "map50": "37.3" },
    { "name": "yolov8s", "description": "Balanced speed and accuracy", "params": "11.2M", "speed": "~12ms", "map50": "44.9" },
    { "name": "yolov8m", "description": "Higher accuracy", "params": "25.9M", "speed": "~26ms", "map50": "50.2" }
  ],
  "current_default": "yolov8n"
}
```

---

### `GET /health` and `GET /metrics`

```bash
curl http://localhost:8000/health
curl http://localhost:8000/metrics
```

---

### `WS /ws/detect` — Real-time WebSocket

**Protocol**

1. Connect to `ws://localhost:8000/ws/detect`
2. Send handshake (text):
   ```json
   { "model": "yolov8n", "confidence_threshold": 0.25 }
   ```
3. Send frames as **binary** (raw JPEG bytes) **or** as **text** (base64 JSON):
   ```json
   { "frame_id": 42, "image": "<base64-encoded-jpeg>" }
   ```
4. Receive detections per frame:
   ```json
   { "objects": [...], "count": 3, "inference_time_ms": 7.1, "frame_id": 42 }
   ```

**Demo client (image loop)**
```bash
python scripts/ws_client_demo.py --image photo.jpg --frames 50
```

**Demo client (live webcam)**
```bash
pip install opencv-python websockets
python scripts/ws_client_demo.py --webcam
```

---

## API Key Authentication

Set `API_KEY=mysecret` in `.env`, then include the header on every detection request:

```bash
curl -X POST http://localhost:8000/detect \
  -H "X-API-Key: mysecret" \
  -F "file=@photo.jpg"
```

Leave `API_KEY` blank (default) to disable auth entirely.

---

## Deployment

### Railway (one-click)

```bash
railway init
railway up
```

### Render

1. Connect your GitHub repo
2. Set environment: `Docker`
3. Add env var `API_KEY` in dashboard
4. Deploy

### Hugging Face Spaces (free GPU)

Create a Space with `Docker` SDK, push this repo. Set hardware to `T4 GPU` for GPU inference.

### AWS EC2

```bash
# On EC2 (Amazon Linux 2)
sudo yum install docker -y
sudo service docker start
docker compose up -d
```

---

## Project Structure

```
object-detection-api/
├── app/
│   ├── main.py         # FastAPI app — REST + WebSocket endpoints
│   ├── detector.py     # YOLOv8 wrapper (lazy-load, thread-safe, multi-model)
│   ├── schemas.py      # Pydantic request/response models
│   └── utils.py        # Image decoding helpers
├── scripts/
│   ├── benchmark.py    # Model speed benchmark → markdown table
│   └── ws_client_demo.py # WebSocket demo client (image loop + webcam)
├── tests/
│   ├── test_api.py     # FastAPI endpoint tests
│   └── test_utils.py   # Utility unit tests
├── models/             # YOLOv8 .pt weights (auto-downloaded, gitignored)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## Running Tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

---

## Environment Variables

| Variable          | Default | Description                                      |
|-------------------|---------|--------------------------------------------------|
| `API_KEY`         | *(none)*| Optional API key — leave blank to disable auth   |
| `ALLOWED_ORIGINS` | `*`     | Comma-separated CORS origins                     |
| `DEFAULT_MODEL`   | `yolov8n` | Model to pre-warm at startup                  |

---

## Tech Stack

| Layer      | Technology                         |
|------------|------------------------------------|
| Model      | YOLOv8 (Ultralytics)               |
| API        | FastAPI + Uvicorn                  |
| Real-time  | WebSocket (native FastAPI)         |
| Inference  | PyTorch (CPU/GPU auto-detect)      |
| Validation | Pydantic v2                        |
| Rate limit | slowapi                            |
| Container  | Docker + docker-compose            |
| Testing    | pytest + FastAPI TestClient        |

---

## License

MIT
