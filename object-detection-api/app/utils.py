import io
import base64
import httpx
from PIL import Image
import numpy as np


def bytes_to_image(data: bytes) -> Image.Image:
    """Convert raw bytes to PIL Image."""
    return Image.open(io.BytesIO(data)).convert("RGB")


def base64_to_image(b64_string: str) -> Image.Image:
    """Convert base64-encoded string to PIL Image."""
    # Strip data URI prefix if present (e.g. "data:image/jpeg;base64,...")
    if "," in b64_string:
        b64_string = b64_string.split(",", 1)[1]
    data = base64.b64decode(b64_string)
    return bytes_to_image(data)


def image_to_base64(image: Image.Image, fmt: str = "JPEG") -> str:
    """Convert PIL Image to base64 string."""
    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


async def fetch_image_from_url(url: str) -> Image.Image:
    """Download an image from a URL and return as PIL Image."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if not content_type.startswith("image/"):
            raise ValueError(f"URL did not return an image (content-type: {content_type})")
        return bytes_to_image(response.content)


def image_to_numpy(image: Image.Image) -> np.ndarray:
    """Convert PIL Image to numpy array (RGB)."""
    return np.array(image)
