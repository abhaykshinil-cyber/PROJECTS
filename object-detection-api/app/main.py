"""
Real-time Object Detection API
FastAPI + YOLOv8 + WebSocket

Endpoints:
  POST /detect          — upload image file, get detections
  POST /detect/url      — pass image URL, get detections
  GET  /models          — list available models + metadata
  GET  /health          — liveness check
  GET  /metrics         — aggregate request statistics
  WS   /ws/detect       — WebSocket for real-time frame streaming
"""
import asyncio
import json
import logging
import os
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.detector import MODEL_METADATA, detector
from app.schemas import (
    DetectUrlRequest,
    DetectionResponse,
    ErrorResponse,
    HealthResponse,
    MetricsResponse,
    ModelInfo,
    ModelName,
    ModelsResponse,
    WebSocketFrame,
)
from app.utils import base64_to_image, bytes_to_image, fetch_image_from_url

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory metrics (process-local; use Redis for multi-worker setups)
# ---------------------------------------------------------------------------
_metrics: dict = {
    "total_requests": 0,
    "total_detections": 0,
    "inference_times_ms": [],
    "requests_per_model": defaultdict(int),
}


def _record(model_name: str, n_detections: int, inference_ms: float) -> None:
    _metrics["total_requests"] += 1
    _metrics["total_detections"] += n_detections
    _metrics["inference_times_ms"].append(inference_ms)
    _metrics["requests_per_model"][model_name] += 1


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

# ---------------------------------------------------------------------------
# Optional API key auth
# ---------------------------------------------------------------------------
API_KEY = os.getenv("API_KEY")  # if unset, auth is disabled


def verify_api_key(request: Request) -> None:
    if API_KEY is None:
        return  # auth disabled
    key = request.headers.get("X-API-Key")
    if key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
        )


# ---------------------------------------------------------------------------
# Lifespan — pre-warm default model on startup
# ---------------------------------------------------------------------------
def _default_model() -> ModelName:
    val = os.getenv("DEFAULT_MODEL", ModelName.nano.value)
    try:
        return ModelName(val)
    except ValueError:
        logger.warning("Unknown DEFAULT_MODEL=%r, falling back to nano", val)
        return ModelName.nano


@asynccontextmanager
async def lifespan(app: FastAPI):
    default = _default_model()
    logger.info("Pre-warming default model (%s) ...", default.value)
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: detector._load_model(default))
    logger.info("Startup complete.")
    yield
    logger.info("Shutting down.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Real-time Object Detection API",
    description=(
        "YOLOv8-powered REST + WebSocket API for real-time object detection. "
        "Supports multiple model sizes (nano / small / medium), live frame streaming "
        "over WebSocket, and per-model benchmarking metrics."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helper — run blocking inference in a thread pool
# ---------------------------------------------------------------------------
async def _run_detect(image, model_name: str, conf: float):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, lambda: detector.detect(image, model_name=model_name, confidence_threshold=conf)
    )


# ---------------------------------------------------------------------------
# REST Endpoints
# ---------------------------------------------------------------------------


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health():
    """Liveness check — returns loaded models and compute device."""
    return HealthResponse(
        status="ok",
        models_loaded=detector.loaded_models(),
        device=detector.device(),
    )


@app.get("/metrics", response_model=MetricsResponse, tags=["System"])
async def metrics():
    """Aggregate request and detection statistics."""
    times = _metrics["inference_times_ms"]
    avg = round(sum(times) / len(times), 2) if times else 0.0
    return MetricsResponse(
        total_requests=_metrics["total_requests"],
        total_detections=_metrics["total_detections"],
        average_inference_ms=avg,
        requests_per_model=dict(_metrics["requests_per_model"]),
    )


@app.get("/models", response_model=ModelsResponse, tags=["Models"])
async def list_models():
    """List available YOLOv8 models with speed and accuracy metadata."""
    models = [
        ModelInfo(
            name=name,
            description=meta["description"],
            params=meta["params"],
            speed=meta["speed"],
            map50=meta["map50"],
        )
        for name, meta in MODEL_METADATA.items()
    ]
    return ModelsResponse(models=models, current_default=ModelName.nano)


@app.post(
    "/detect",
    response_model=DetectionResponse,
    tags=["Detection"],
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit("30/minute")
async def detect_image(
    request: Request,
    file: UploadFile = File(..., description="Image file (JPEG, PNG, WebP, BMP)"),
    model: ModelName = Form(ModelName.nano),
    confidence_threshold: float = Form(0.25),
):
    """
    Upload an image file and receive detected objects.

    - **file**: image upload (JPEG / PNG / WebP / BMP)
    - **model**: `yolov8n` (default) | `yolov8s` | `yolov8m`
    - **confidence_threshold**: minimum confidence to include a detection (0–1)
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"File must be an image. Got content-type: {file.content_type}",
        )

    raw = await file.read()
    try:
        image = bytes_to_image(raw)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Cannot decode image: {exc}") from exc

    detections, inference_ms = await _run_detect(image, model, confidence_threshold)
    _record(model, len(detections), inference_ms)

    return DetectionResponse(
        objects=detections,
        count=len(detections),
        model_used=model,
        inference_time_ms=inference_ms,
        image_width=image.width,
        image_height=image.height,
    )


@app.post(
    "/detect/url",
    response_model=DetectionResponse,
    tags=["Detection"],
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit("30/minute")
async def detect_url(request: Request, body: DetectUrlRequest):
    """
    Pass a public image URL and receive detected objects.
    """
    try:
        image = await fetch_image_from_url(str(body.url))
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to fetch image: {exc}") from exc

    detections, inference_ms = await _run_detect(image, body.model, body.confidence_threshold)
    _record(body.model, len(detections), inference_ms)

    return DetectionResponse(
        objects=detections,
        count=len(detections),
        model_used=body.model,
        inference_time_ms=inference_ms,
        image_width=image.width,
        image_height=image.height,
    )


# ---------------------------------------------------------------------------
# WebSocket — Real-time frame streaming
# ---------------------------------------------------------------------------


@app.websocket("/ws/detect")
async def websocket_detect(websocket: WebSocket):
    """
    WebSocket endpoint for real-time object detection on video frames.

    **Client protocol**:
    1. Connect to `ws://<host>/ws/detect`
    2. Send a JSON handshake:
       ```json
       { "model": "yolov8n", "confidence_threshold": 0.25 }
       ```
    3. Then send frames as **binary messages** (raw JPEG/PNG bytes)
       OR as **text messages** with base64-encoded image:
       ```json
       { "frame_id": 1, "image": "<base64>" }
       ```
    4. Receive JSON detections per frame:
       ```json
       { "objects": [...], "count": 5, "inference_time_ms": 8.3, "frame_id": 1 }
       ```

    Send `{ "action": "ping" }` to check connection. Receive `{ "action": "pong" }`.
    """
    await websocket.accept()
    logger.info("WebSocket client connected: %s", websocket.client)

    # --- Handshake ---
    model_name: str = ModelName.nano
    conf_threshold: float = 0.25

    try:
        handshake_raw = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
        handshake = json.loads(handshake_raw)
        model_name = handshake.get("model", ModelName.nano)
        conf_threshold = float(handshake.get("confidence_threshold", 0.25))

        # Validate model name
        valid_models = [m.value for m in ModelName]
        if model_name not in valid_models:
            await websocket.send_json({"error": f"Unknown model. Choose from {valid_models}"})
            await websocket.close()
            return

        await websocket.send_json({"status": "ready", "model": model_name, "conf": conf_threshold})
        logger.info("WS handshake OK — model=%s conf=%.2f", model_name, conf_threshold)

    except asyncio.TimeoutError:
        await websocket.send_json({"error": "Handshake timeout (10s)"})
        await websocket.close()
        return
    except (json.JSONDecodeError, KeyError) as exc:
        await websocket.send_json({"error": f"Invalid handshake: {exc}"})
        await websocket.close()
        return

    # --- Frame loop ---
    loop = asyncio.get_event_loop()
    try:
        while True:
            message = await websocket.receive()

            # Ping/pong control message
            if message.get("type") == "websocket.receive" and message.get("text"):
                try:
                    ctrl = json.loads(message["text"])
                    if ctrl.get("action") == "ping":
                        await websocket.send_json({"action": "pong"})
                        continue

                    # Text frame: base64 image
                    frame_id: Optional[int] = ctrl.get("frame_id")
                    b64 = ctrl.get("image", "")
                    image = base64_to_image(b64)

                except (json.JSONDecodeError, Exception) as exc:
                    await websocket.send_json({"error": f"Invalid text frame: {exc}"})
                    continue

            elif message.get("type") == "websocket.receive" and message.get("bytes"):
                # Binary frame: raw image bytes
                frame_id = None
                try:
                    image = bytes_to_image(message["bytes"])
                except Exception as exc:
                    await websocket.send_json({"error": f"Cannot decode image: {exc}"})
                    continue

            elif message.get("type") == "websocket.disconnect":
                break

            else:
                continue

            # Run detection (offload to thread pool so we don't block the event loop)
            detections, inference_ms = await loop.run_in_executor(
                None,
                lambda: detector.detect(image, model_name=model_name, confidence_threshold=conf_threshold),
            )
            _record(model_name, len(detections), inference_ms)

            response = WebSocketFrame(
                objects=detections,
                count=len(detections),
                inference_time_ms=inference_ms,
                frame_id=frame_id,
            )
            await websocket.send_text(response.model_dump_json())

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected: %s", websocket.client)
    except Exception as exc:
        logger.exception("WebSocket error: %s", exc)
        try:
            await websocket.send_json({"error": str(exc)})
        except Exception:
            pass
