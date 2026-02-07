# image_utils.py
import base64
from typing import Optional

def image_to_base64(image_bytes: bytes) -> str:
    """
    Convert raw image bytes (JPEG/PNG) to Base64 string
    """
    return base64.b64encode(image_bytes).decode("utf-8")

def parse_base64_from_json(data: dict) -> Optional[str]:
    """
    Extract image Base64 from JSON payload sent by client
    """
    return data.get("image")
