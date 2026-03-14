#!/usr/bin/env python3
"""
Benchmark YOLOv8 models and print a markdown table.

Usage:
    python scripts/benchmark.py [--image path/to/image.jpg] [--runs 20]
"""
import argparse
import io
import statistics
import sys
import time
from pathlib import Path

# Make sure the project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from PIL import Image

from app.detector import ObjectDetector
from app.schemas import ModelName


def _load_image(path: str | None) -> Image.Image:
    if path:
        return Image.open(path).convert("RGB")
    # Generate a synthetic 640x480 image if none provided
    return Image.new("RGB", (640, 480), color=(100, 149, 237))


def benchmark(image: Image.Image, runs: int = 20) -> None:
    det = ObjectDetector()
    models = [ModelName.nano, ModelName.small, ModelName.medium]

    print(f"\nBenchmarking {len(models)} models over {runs} runs each ...\n")

    rows = []
    for model_name in models:
        # Warm-up
        det.detect(image, model_name=model_name)

        times = []
        total_objects = 0
        for _ in range(runs):
            objs, ms = det.detect(image, model_name=model_name)
            times.append(ms)
            total_objects += len(objs)

        avg = statistics.mean(times)
        p95 = sorted(times)[int(0.95 * runs) - 1]
        fps = round(1000 / avg, 1)
        rows.append((model_name, avg, p95, fps, total_objects // runs))

    # Print markdown table
    header = "| Model     | Avg ms | P95 ms | FPS (est.) | Avg detections |"
    sep    = "|-----------|--------|--------|------------|----------------|"
    print(header)
    print(sep)
    for model, avg, p95, fps, n in rows:
        print(f"| {model:<9} | {avg:>6.1f} | {p95:>6.1f} | {fps:>10} | {n:>14} |")
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark YOLOv8 models")
    parser.add_argument("--image", help="Path to image file (uses synthetic if omitted)")
    parser.add_argument("--runs", type=int, default=20, help="Inference runs per model")
    args = parser.parse_args()

    img = _load_image(args.image)
    benchmark(img, runs=args.runs)
