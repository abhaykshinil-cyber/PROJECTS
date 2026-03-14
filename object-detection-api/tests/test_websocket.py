"""
WebSocket tests for /ws/detect endpoint.

Run with:  pytest tests/test_websocket.py -v
"""
import base64
import io
import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.schemas import BoundingBox, DetectedObject


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _make_jpeg_bytes(width: int = 320, height: int = 240) -> bytes:
    img = Image.new("RGB", (width, height), color=(50, 100, 150))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _make_b64_frame(frame_id: int = 0) -> str:
    return json.dumps({
        "frame_id": frame_id,
        "image": base64.b64encode(_make_jpeg_bytes()).decode(),
    })


def _mock_detections():
    return (
        [DetectedObject(
            label="car",
            confidence=0.87,
            bbox=BoundingBox(x1=5.0, y1=10.0, x2=100.0, y2=200.0),
        )],
        5.2,
    )


# ---------------------------------------------------------------------------
# Handshake tests
# ---------------------------------------------------------------------------


def test_ws_handshake_valid(client):
    with client.websocket_connect("/ws/detect") as ws:
        ws.send_text(json.dumps({"model": "yolov8n", "confidence_threshold": 0.3}))
        resp = ws.receive_json()
        assert resp["status"] == "ready"
        assert resp["model"] == "yolov8n"
        assert resp["conf"] == 0.3


def test_ws_handshake_default_conf(client):
    with client.websocket_connect("/ws/detect") as ws:
        ws.send_text(json.dumps({"model": "yolov8n"}))
        resp = ws.receive_json()
        assert resp["status"] == "ready"
        assert resp["conf"] == 0.25


def test_ws_handshake_invalid_model(client):
    with client.websocket_connect("/ws/detect") as ws:
        ws.send_text(json.dumps({"model": "yolov8xxl"}))
        resp = ws.receive_json()
        assert "error" in resp


def test_ws_handshake_invalid_json(client):
    with client.websocket_connect("/ws/detect") as ws:
        ws.send_text("not-json")
        resp = ws.receive_json()
        assert "error" in resp


# ---------------------------------------------------------------------------
# Frame detection tests
# ---------------------------------------------------------------------------


@patch("app.main.detector.detect", return_value=_mock_detections())
def test_ws_base64_frame(mock_detect, client):
    with client.websocket_connect("/ws/detect") as ws:
        ws.send_text(json.dumps({"model": "yolov8n", "confidence_threshold": 0.25}))
        ws.receive_json()  # ready

        ws.send_text(_make_b64_frame(frame_id=1))
        result = ws.receive_json()

        assert result["count"] == 1
        assert result["frame_id"] == 1
        assert result["objects"][0]["label"] == "car"
        assert "inference_time_ms" in result


@patch("app.main.detector.detect", return_value=_mock_detections())
def test_ws_binary_frame(mock_detect, client):
    with client.websocket_connect("/ws/detect") as ws:
        ws.send_text(json.dumps({"model": "yolov8n", "confidence_threshold": 0.25}))
        ws.receive_json()  # ready

        ws.send_bytes(_make_jpeg_bytes())
        result = ws.receive_json()

        assert result["count"] == 1
        assert result["frame_id"] is None
        assert result["objects"][0]["label"] == "car"


@patch("app.main.detector.detect", return_value=_mock_detections())
def test_ws_multiple_frames(mock_detect, client):
    with client.websocket_connect("/ws/detect") as ws:
        ws.send_text(json.dumps({"model": "yolov8n", "confidence_threshold": 0.25}))
        ws.receive_json()  # ready

        for i in range(5):
            ws.send_text(_make_b64_frame(frame_id=i))
            result = ws.receive_json()
            assert result["frame_id"] == i
            assert result["count"] == 1


# ---------------------------------------------------------------------------
# Ping / pong
# ---------------------------------------------------------------------------


def test_ws_ping_pong(client):
    with client.websocket_connect("/ws/detect") as ws:
        ws.send_text(json.dumps({"model": "yolov8n"}))
        ws.receive_json()  # ready

        ws.send_text(json.dumps({"action": "ping"}))
        resp = ws.receive_json()
        assert resp == {"action": "pong"}


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_ws_invalid_base64_image(client):
    with client.websocket_connect("/ws/detect") as ws:
        ws.send_text(json.dumps({"model": "yolov8n"}))
        ws.receive_json()  # ready

        ws.send_text(json.dumps({"frame_id": 0, "image": "not-valid-base64!!!"}))
        resp = ws.receive_json()
        assert "error" in resp


def test_ws_corrupt_binary_frame(client):
    with client.websocket_connect("/ws/detect") as ws:
        ws.send_text(json.dumps({"model": "yolov8n"}))
        ws.receive_json()  # ready

        ws.send_bytes(b"\xff\xd8corrupt-jpeg-data")
        resp = ws.receive_json()
        assert "error" in resp


# ---------------------------------------------------------------------------
# All three model names work
# ---------------------------------------------------------------------------


@patch("app.main.detector.detect", return_value=([], 3.0))
def test_ws_all_model_names(mock_detect, client):
    for model in ("yolov8n", "yolov8s", "yolov8m"):
        with client.websocket_connect("/ws/detect") as ws:
            ws.send_text(json.dumps({"model": model}))
            resp = ws.receive_json()
            assert resp["status"] == "ready"
            assert resp["model"] == model
