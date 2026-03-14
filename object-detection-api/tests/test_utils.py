"""Unit tests for utility functions."""
import base64
import io

import pytest
from PIL import Image

from app.utils import base64_to_image, bytes_to_image, image_to_base64, image_to_numpy


def _rgb_image(w: int = 100, h: int = 80) -> Image.Image:
    return Image.new("RGB", (w, h), color=(255, 0, 0))


def _image_to_bytes(img: Image.Image, fmt: str = "JPEG") -> bytes:
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# bytes_to_image
# ---------------------------------------------------------------------------


def test_bytes_to_image_jpeg():
    raw = _image_to_bytes(_rgb_image(), "JPEG")
    img = bytes_to_image(raw)
    assert isinstance(img, Image.Image)
    assert img.mode == "RGB"


def test_bytes_to_image_png():
    raw = _image_to_bytes(_rgb_image(), "PNG")
    img = bytes_to_image(raw)
    assert img.mode == "RGB"


def test_bytes_to_image_invalid():
    with pytest.raises(Exception):
        bytes_to_image(b"not-an-image")


# ---------------------------------------------------------------------------
# base64_to_image
# ---------------------------------------------------------------------------


def test_base64_to_image_plain():
    raw = _image_to_bytes(_rgb_image(), "JPEG")
    b64 = base64.b64encode(raw).decode()
    img = base64_to_image(b64)
    assert img.size == (100, 80)


def test_base64_to_image_data_uri():
    raw = _image_to_bytes(_rgb_image(), "JPEG")
    b64 = base64.b64encode(raw).decode()
    data_uri = f"data:image/jpeg;base64,{b64}"
    img = base64_to_image(data_uri)
    assert img.size == (100, 80)


# ---------------------------------------------------------------------------
# image_to_base64
# ---------------------------------------------------------------------------


def test_image_to_base64_roundtrip():
    original = _rgb_image(50, 50)
    b64 = image_to_base64(original, fmt="PNG")
    decoded = base64_to_image(b64)
    assert decoded.size == original.size


# ---------------------------------------------------------------------------
# image_to_numpy
# ---------------------------------------------------------------------------


def test_image_to_numpy_shape():
    img = _rgb_image(64, 32)
    arr = image_to_numpy(img)
    assert arr.shape == (32, 64, 3)


def test_image_to_numpy_dtype():
    import numpy as np
    arr = image_to_numpy(_rgb_image())
    assert arr.dtype == np.uint8
