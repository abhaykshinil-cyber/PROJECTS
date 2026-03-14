"""Download all YOLOv8 model weights into /app/models during Docker build."""
import os
import shutil
from pathlib import Path

os.environ.setdefault("YOLO_CONFIG_DIR", "/app/models")

from ultralytics import YOLO  # noqa: E402

MODELS_DIR = Path("/app/models")
MODELS_DIR.mkdir(parents=True, exist_ok=True)

for model_file in ["yolov8n.pt", "yolov8s.pt", "yolov8m.pt"]:
    dst = MODELS_DIR / model_file
    model = YOLO(model_file)
    src = Path(model.ckpt_path)
    if src.exists() and src != dst:
        shutil.copy(str(src), str(dst))
        print(f"Copied {src} -> {dst}")
    elif dst.exists():
        print(f"Already at {dst}")
    else:
        print(f"WARNING: could not locate {model_file}")

print("All models ready.")
