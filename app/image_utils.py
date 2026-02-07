import base64
import json
from typing import Dict

def parse_image_from_json(data: str) -> bytes:
    """
    Extract raw image bytes from JSON containing base64.
    Expected input: {"image": "<base64 string>"}
    """
    try:
        parsed = json.loads(data)
        img_b64 = parsed.get("image")
        if not img_b64:
            raise ValueError("No 'image' key found in JSON")
        return base64.b64decode(img_b64)
    except Exception as e:
        print(f"[image_utils] Failed to parse image JSON: {e}")
        raise

def encode_image_to_base64(img_bytes: bytes) -> str:
   
    return base64.b64encode(img_bytes).decode("utf-8")
