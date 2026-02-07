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
        parts = []
        
        # 1. Image context
        if image_b64:
            parts.append({"inline_data": {"mime_type": "image/jpeg", "data": image_b64}})

        # 2. Sequential audio chunks
        for chunk in audio_list:
            parts.append({
                "inline_data": {
                    "mime_type": "audio/pcm;rate=16000",
                    "data": chunk
                }
            })

        # 3. System Instruction
        parts.append({
            "text": (
                "You are an AI Handyman. Using the image and audio, provide short, "
                "safe repair steps. Use 'SAFETY WARNING' if you see hazards."
            )
        })

        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {"temperature": 0.4, "max_output_tokens": 150}
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(self.url, json=payload, timeout=30.0)
                return response.json() if response.status_code == 200 else None
            except Exception as e:
                logger.error(f"Gemini Request Failed: {e}")
                return None
