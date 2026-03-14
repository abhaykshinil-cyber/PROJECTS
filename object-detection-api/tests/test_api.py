"""
Integration tests for the Object Detection API.

Run with:  pytest tests/ -v
"""
import io
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.schemas import BoundingBox, DetectedObject


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _make_image_bytes(width: int = 640, height: int = 480, fmt: str = "JPEG") -> bytes:
    """Generate a synthetic solid-color image as bytes."""
    img = Image.new("RGB", (width, height), color=(100, 149, 237))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def _mock_detections():
    return (
        [
            DetectedObject(
                label="person",
                confidence=0.91,
                bbox=BoundingBox(x1=10.0, y1=20.0, x2=200.0, y2=400.0),
            )
        ],
        8.5,  # inference_ms
    )


# ---------------------------------------------------------------------------
# Health / Metrics / Models
# ---------------------------------------------------------------------------


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "device" in body
    assert isinstance(body["models_loaded"], list)


def test_metrics_initial(client):
    resp = client.get("/metrics")
    assert resp.status_code == 200
    body = resp.json()
    assert "total_requests" in body
    assert "average_inference_ms" in body


def test_list_models(client):
    resp = client.get("/models")
    assert resp.status_code == 200
    body = resp.json()
    assert "models" in body
    names = [m["name"] for m in body["models"]]
    assert "yolov8n" in names
    assert "yolov8s" in names
    assert "yolov8m" in names


# ---------------------------------------------------------------------------
# POST /detect (file upload)
# ---------------------------------------------------------------------------


@patch("app.main.detector.detect", return_value=_mock_detections())
def test_detect_image_success(mock_detect, client):
    img_bytes = _make_image_bytes()
    resp = client.post(
        "/detect",
        files={"file": ("test.jpg", img_bytes, "image/jpeg")},
        data={"model": "yolov8n", "confidence_threshold": "0.25"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["objects"][0]["label"] == "person"
    assert body["model_used"] == "yolov8n"
    assert "inference_time_ms" in body


@patch("app.main.detector.detect", return_value=_mock_detections())
def test_detect_image_png(mock_detect, client):
    img_bytes = _make_image_bytes(fmt="PNG")
    resp = client.post(
        "/detect",
        files={"file": ("test.png", img_bytes, "image/png")},
    )
    assert resp.status_code == 200


def test_detect_invalid_content_type(client):
    resp = client.post(
        "/detect",
        files={"file": ("data.txt", b"not an image", "text/plain")},
    )
    assert resp.status_code == 422


def test_detect_corrupt_image(client):
    resp = client.post(
        "/detect",
        files={"file": ("bad.jpg", b"\xff\xd8corrupt", "image/jpeg")},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /detect/url
# ---------------------------------------------------------------------------


@patch("app.main.fetch_image_from_url")
@patch("app.main.detector.detect", return_value=_mock_detections())
def test_detect_url_success(mock_detect, mock_fetch, client):
    mock_fetch.return_value = Image.new("RGB", (640, 480))
    resp = client.post(
        "/detect/url",
        json={"url": "http://example.com/image.jpg", "model": "yolov8n"},
    )
    assert resp.status_code == 200
    assert resp.json()["count"] == 1


@patch("app.main.fetch_image_from_url", side_effect=Exception("connection error"))
def test_detect_url_fetch_failure(mock_fetch, client):
    resp = client.post(
        "/detect/url",
        json={"url": "http://example.com/image.jpg"},
    )
    assert resp.status_code == 422


def test_detect_url_invalid_url(client):
    resp = client.post("/detect/url", json={"url": "not-a-url"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Metrics update after requests
# ---------------------------------------------------------------------------


@patch("app.main.detector.detect", return_value=_mock_detections())
def test_metrics_update(mock_detect, client):
    before = client.get("/metrics").json()["total_requests"]
    img_bytes = _make_image_bytes()
    client.post(
        "/detect",
        files={"file": ("test.jpg", img_bytes, "image/jpeg")},
    )
    after = client.get("/metrics").json()["total_requests"]
    assert after == before + 1
