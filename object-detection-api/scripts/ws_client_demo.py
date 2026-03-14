#!/usr/bin/env python3
"""
Demo WebSocket client — streams frames from a local image or webcam.

Usage:
    # Stream a single image repeatedly (demo mode)
    python scripts/ws_client_demo.py --image path/to/image.jpg --frames 30

    # Stream from webcam (requires OpenCV)
    python scripts/ws_client_demo.py --webcam
"""
import argparse
import asyncio
import base64
import io
import json
import sys
from pathlib import Path

import websockets
from PIL import Image


def _encode_frame(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()


async def stream_image(url: str, image_path: str, frames: int, model: str) -> None:
    async with websockets.connect(url) as ws:
        # Handshake
        await ws.send(json.dumps({"model": model, "confidence_threshold": 0.25}))
        ready = json.loads(await ws.recv())
        print(f"Server ready: {ready}")

        img = Image.open(image_path).convert("RGB")
        for i in range(frames):
            payload = json.dumps({"frame_id": i, "image": _encode_frame(img)})
            await ws.send(payload)
            result = json.loads(await ws.recv())
            n = result.get("count", 0)
            ms = result.get("inference_time_ms", "?")
            labels = [o["label"] for o in result.get("objects", [])]
            print(f"Frame {i:>3} | {n} objects | {ms} ms | {labels}")

        print("\nDone.")


async def stream_webcam(url: str, model: str) -> None:
    try:
        import cv2
    except ImportError:
        print("OpenCV not installed. Run: pip install opencv-python")
        sys.exit(1)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Cannot open webcam.")
        sys.exit(1)

    async with websockets.connect(url) as ws:
        await ws.send(json.dumps({"model": model, "confidence_threshold": 0.25}))
        ready = json.loads(await ws.recv())
        print(f"Server ready: {ready}. Press Ctrl+C to stop.\n")

        frame_id = 0
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                payload = json.dumps({"frame_id": frame_id, "image": _encode_frame(img)})
                await ws.send(payload)
                result = json.loads(await ws.recv())
                n = result.get("count", 0)
                ms = result.get("inference_time_ms", "?")
                print(f"\rFrame {frame_id:>4} | {n:>2} objects | {ms:>6} ms", end="", flush=True)
                frame_id += 1
        except KeyboardInterrupt:
            print("\nStopped.")
        finally:
            cap.release()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="ws://localhost:8000/ws/detect")
    parser.add_argument("--model", default="yolov8n")
    parser.add_argument("--image", help="Path to image for demo streaming")
    parser.add_argument("--frames", type=int, default=30)
    parser.add_argument("--webcam", action="store_true")
    args = parser.parse_args()

    if args.webcam:
        asyncio.run(stream_webcam(args.url, args.model))
    elif args.image:
        asyncio.run(stream_image(args.url, args.image, args.frames, args.model))
    else:
        parser.print_help()
