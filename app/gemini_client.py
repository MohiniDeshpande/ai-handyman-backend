import httpx
import json
import logging
from app.config import GEMINI_API_KEY, GEMINI_API_URL, TEXT_MODEL

logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self, api_key: str = GEMINI_API_KEY):
        self.api_key = api_key
        # Gemini 3 Pro 2026 Endpoint
        self.url = f"{GEMINI_API_URL}/models/{TEXT_MODEL}:generateContent?key={self.api_key}"

    async def analyze_handyman_context(self, audio_b64: str = None, image_b64: str = None):
        """
        Processes visual and audio data to provide repair guidance.
        """
        parts = []
        
        # 1. Add Image (Visual Context)
        if image_b64:
            parts.append({
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": image_b64
                }
            })

        # 2. Add Audio (1000ms Voice Context)
        if audio_b64:
            parts.append({
                "inline_data": {
                    "mime_type": "audio/pcm;rate=16000",
                    "data": audio_b64
                }
            })

        # 3. Handyman System Prompt
        parts.append({
            "text": (
                "You are an expert AI Handyman for AR glasses. "
                "Analyze the image and user audio. Provide short, precise repair steps. "
                "If you see a safety hazard (exposed wires, etc.), start with 'SAFETY WARNING'."
            )
        })

        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "thinking_level": "high",  # Gemini 3 deep reasoning
                "media_resolution": "high", 
                "temperature": 0.5,
                "max_output_tokens": 150
            }
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(self.url, json=payload, timeout=30.0)
                if response.status_code != 200:
                    logger.error(f"Gemini API Error: {response.text}")
                    return None
                return response.json()
            except Exception as e:
                logger.error(f"Request Exception: {e}")
                return None
