import json
import base64
from typing import Any, Dict

# ===== Audio utility =====
def pcm16_to_base64(pcm_bytes: bytes) -> str:
    """Convert PCM16 bytes to base64 for sending over JSON."""
    return base64.b64encode(pcm_bytes).decode("utf-8")


# ===== Image / text AI calls =====
# Replace with actual Gemini SDK / API calls
def text_response(conversation: list[dict]) -> dict:
    """
    Call Gemini to get a text response.
    conversation: list of dicts with 'role' and 'parts'.
    """
    # Here, integrate Gemini API
    user_input = conversation[-1]["parts"][0].get("text", "")
    # Example placeholder API call:
    model_reply = f"Gemini response to: {user_input}"
    return {"candidates": [{"content": model_reply}]}


def image_response(conversation: list[dict]) -> dict:
    """
    Call Gemini to get an image response as inline Base64 JSON.
    Returns dict with 'candidates' and 'content' Base64 encoded.
    """
    prompt = conversation[-1]["parts"][0].get("text", "")
    # Call Gemini image API here and get raw image bytes
    # For demonstration, we'll use a dummy PNG byte string
    # Replace this with real Gemini image bytes
    dummy_image_bytes = b"\x89PNG\r\n\x1a\n..."  # Replace with Gemini API result
    image_b64 = base64.b64encode(dummy_image_bytes).decode("utf-8")
    return {"candidates": [{"content": {"mime_type": "image/png", "data": image_b64}}]}

def needs_image(text: str) -> bool:
    triggers = [
        "how does it look",
        "what does it look like",
        "show me",
        "generate an image",
        "can you show",
        "picture of",
        "image of"
    ]
    text = text.lower()
    return any(t in text for t in triggers)

