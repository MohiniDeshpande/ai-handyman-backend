import requests
from typing import Optional, Dict, Any

from .config import (
    GEMINI_API_KEY,
    GEMINI_BASE_URL,
    TEXT_MODEL,
    IMAGE_MODEL,
    AUDIO_MIME_TYPE,
)

HEADERS = {
    "Content-Type": "application/json"
}


class GeminiClient:
    def __init__(self):
        self.api_key = GEMINI_API_KEY

    def _post(self, model: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Low-level POST to Gemini generateContent endpoint
        """
        url = f"{GEMINI_BASE_URL}/{model}:generateContent"

        response = requests.post(
            url,
            headers=HEADERS,
            params={"key": self.api_key},
            json=payload,
            timeout=30,
        )

        response.raise_for_status()
        return response.json()

    def generate(
        self,
        text: Optional[str] = None,
        image_b64: Optional[str] = None,
        audio_b64: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Unified multimodal call.
        - Uses IMAGE_MODEL if image is present
        - Otherwise uses TEXT_MODEL
        """

        parts = []

        if text:
            parts.append({
                "text": text
            })

        if image_b64:
            parts.append({
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": image_b64
                }
            })

        if audio_b64:
            parts.append({
                "inline_data": {
                    "mime_type": AUDIO_MIME_TYPE,
                    "data": audio_b64
                }
            })

        if not parts:
            raise ValueError("No content provided to Gemini")

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": parts
                }
            ]
        }

        model = IMAGE_MODEL if image_b64 else TEXT_MODEL
        return self._post(model, payload)

