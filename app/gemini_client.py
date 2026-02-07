import requests
import logging
from typing import Dict, Any, Optional, List

from .config import (
    GEMINI_API_KEY,
    GEMINI_BASE_URL,
    TEXT_MODEL,
    IMAGE_MODEL,
    AUDIO_MIME_TYPE,
)

logger = logging.getLogger(__name__)

HEADERS = {"Content-Type": "application/json"}


class GeminiClient:
    def __init__(self):
        self.api_key = GEMINI_API_KEY

    def _url(self, model: str) -> str:
        return f"{GEMINI_BASE_URL}/{model}:generateContent"

    def _post(self, model: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"[Gemini] Sending request to model={model}")

        res = requests.post(
            self._url(model),
            headers=HEADERS,
            params={"key": self.api_key},
            json=payload,
            timeout=30,
        )

        logger.info(f"[Gemini] Status={res.status_code}")

        if not res.ok:
            logger.error(res.text)
            res.raise_for_status()

        return res.json()

    def generate(
        self,
        text: Optional[str] = None,
        image_b64: Optional[str] = None,
        audio_b64: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:

        parts = []

        if text:
            parts.append({"text": text})

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
            raise ValueError("No input provided to Gemini")

        contents = history[:] if history else []
        contents.append({
            "role": "user",
            "parts": parts
        })

        payload: Dict[str, Any] = {
            "contents": contents
        }

        if tools:
            payload["tools"] = tools
            payload["tool_config"] = {
                "function_calling_config": {
                    "mode": "AUTO"
                }
            }

        model = IMAGE_MODEL if image_b64 else TEXT_MODEL
        return self._post(model, payload)
