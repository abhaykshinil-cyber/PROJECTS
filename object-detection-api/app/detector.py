"""
YOLOv8 detector wrapper supporting multiple model sizes and ONNX export.
Models are lazy-loaded and cached for performance.
"""
import time
import threading
from pathlib import Path
from typing import Optional
import logging

from PIL import Image

from app.schemas import DetectedObject, BoundingBox, ModelName

logger = logging.getLogger(__name__)

# Directory where .pt weights are stored / cached
MODELS_DIR = Path(__file__).parent.parent / "models"
MODELS_DIR.mkdir(exist_ok=True)

MODEL_METADATA = {
    ModelName.nano: {
        "description": "Fastest, smallest model — great for real-time use",
        "params": "3.2M",
        "speed": "~6ms",
        "map50": "37.3",
    },
    ModelName.small: {
        "description": "Balanced speed and accuracy",
        "params": "11.2M",
        "speed": "~12ms",
        "map50": "44.9",
    },
    ModelName.medium: {
        "description": "Higher accuracy, suitable for offline batch jobs",
        "params": "25.9M",
        "speed": "~26ms",
        "map50": "50.2",
    },
}


class ObjectDetector:
    """Thread-safe YOLOv8 detector with lazy model loading and caching."""

    def __init__(self) -> None:
        self._models: dict[str, object] = {}
        self._lock = threading.Lock()
        self._device: Optional[str] = None

    def _resolve_device(self) -> str:
        if self._device is None:
            try:
                import torch
                self._device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                self._device = "cpu"
        return self._device

    def _load_model(self, model_name: str) -> object:
        """Load and cache a YOLO model. Downloads weights on first use."""
        if model_name not in self._models:
            with self._lock:
                if model_name not in self._models:
                    from ultralytics import YOLO
                    weight_path = MODELS_DIR / f"{model_name.value}.pt"
                    logger.info("Loading model %s ...", model_name.value)
                    model = YOLO(str(weight_path) if weight_path.exists() else f"{model_name.value}.pt")
                    # Move to correct device
                    device = self._resolve_device()
                    model.to(device)
                    self._models[model_name] = model
                    logger.info("Model %s loaded on %s", model_name.value, device)
        return self._models[model_name]

    def detect(
        self,
        image: Image.Image,
        model_name: str = ModelName.nano,
        confidence_threshold: float = 0.25,
    ) -> tuple[list[DetectedObject], float]:
        """
        Run object detection on a PIL Image.

        Returns:
            (list of DetectedObject, inference_time_ms)
        """
        model = self._load_model(model_name)

        start = time.perf_counter()
        results = model(image, conf=confidence_threshold, verbose=False)[0]
        elapsed_ms = (time.perf_counter() - start) * 1000

        detections: list[DetectedObject] = []
        for box in results.boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            detections.append(
                DetectedObject(
                    label=model.names[int(box.cls)],
                    confidence=round(float(box.conf), 4),
                    bbox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2),
                )
            )

        return detections, round(elapsed_ms, 2)

    def loaded_models(self) -> list[str]:
        return list(self._models.keys())

    def device(self) -> str:
        return self._resolve_device()


# Module-level singleton — shared across all requests
detector = ObjectDetector()
