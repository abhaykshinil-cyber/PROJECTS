from pydantic import BaseModel, Field, HttpUrl
from typing import Optional
from enum import Enum


class ModelName(str, Enum):
    nano = "yolov8n"
    small = "yolov8s"
    medium = "yolov8m"


class BoundingBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float


class DetectedObject(BaseModel):
    label: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    bbox: BoundingBox


class DetectionResponse(BaseModel):
    objects: list[DetectedObject]
    count: int
    model_used: str
    inference_time_ms: float
    image_width: int
    image_height: int


class DetectUrlRequest(BaseModel):
    url: HttpUrl
    model: ModelName = ModelName.nano
    confidence_threshold: float = Field(default=0.25, ge=0.0, le=1.0)


class ModelInfo(BaseModel):
    name: str
    description: str
    params: str
    speed: str
    map50: str


class ModelsResponse(BaseModel):
    models: list[ModelInfo]
    current_default: str


class HealthResponse(BaseModel):
    status: str
    models_loaded: list[str]
    device: str


class MetricsResponse(BaseModel):
    total_requests: int
    total_detections: int
    average_inference_ms: float
    requests_per_model: dict[str, int]


class WebSocketFrame(BaseModel):
    """Message format for WebSocket clients."""
    objects: list[DetectedObject]
    count: int
    inference_time_ms: float
    frame_id: Optional[int] = None


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
