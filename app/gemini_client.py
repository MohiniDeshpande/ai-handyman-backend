import httpx
import json
import logging
from app.config import GEMINI_API_KEY, GEMINI_API_URL, TEXT_MODEL

logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self, api_key: str = GEMINI_API_KEY):
        self.api_key = api_key
        self.url = f"{GEMINI_API_URL}/models/{TEXT_MODEL}:generateContent?key={self.api_key}"

    async def analyze_handyman_context(self, audio_list: list, image_b64: str = None):
        """
        Sends accumulated audio chunks and the latest video frame to Gemini.
        """
        parts = []
        
        # 1. Add Visual Context
        if image_b64:
            parts.append({
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": image_b64
                }
            })

        # 2. Add Audio Sequence (PCM 16k)
        for chunk in audio_list:
            parts.append({
                "inline_data": {
                    "mime_type": "audio/pcm;rate=16000",
                    "data": chunk
                }
            })

        # 3. System Instructions
        parts.append({
            "text": (
                "You are an expert AI Handyman for AR glasses. Analyze the image and audio provided. "
                "Provide short, technical repair advice (max 2 sentences). "
                "If you see a safety hazard, include the words 'SAFETY WARNING'."
            )
        })

        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "temperature": 0.4,
                "max_output_tokens": 150
            }
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(self.url, json=payload, timeout=30.0)
                if response.status_code == 200:
                    return response.json()
                logger.error(f"Gemini API Error: {response.text}")
                return None
            except Exception as e:
                logger.error(f"Request Exception: {e}")
                return None
