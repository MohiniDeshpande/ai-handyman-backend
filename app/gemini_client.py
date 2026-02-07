import httpx
import json
from .config import GEMINI_API_KEY, GEMINI_API_URL, TEXT_MODEL, IMAGE_MODEL, THINKING_LEVEL, MEDIA_RESOLUTION

class GeminiClient:
    def __init__(self, api_key: str = GEMINI_API_KEY):
        self.api_key = api_key
        self.base_url = f"{GEMINI_API_URL}/models"

    async def analyze_multimodal(self, text: str = None, audio_b64: str = None, image_b64: str = None):
        """Processes real-time handyman context using Gemini 3 Pro Preview."""
        url = f"{self.base_url}/{TEXT_MODEL}:generateContent?key={self.api_key}"
        
        parts = []
        if text: parts.append({"text": text})
        if image_b64:
            parts.append({"inline_data": {"mime_type": "image/jpeg", "data": image_b64}})
        if audio_b64:
            parts.append({"inline_data": {"mime_type": f"audio/pcm;rate=16000", "data": audio_b64}})

        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "thinking_level": THINKING_LEVEL, # 2026 Thinking control
                "media_resolution": MEDIA_RESOLUTION # 2026 Vision control
            }
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=60.0)
            response.raise_for_status()
            return response.json()

    async def generate_handyman_visual(self, prompt: str):
        """Generates repair diagrams/visuals using Gemini 3 Pro Image Preview."""
        url = f"{self.base_url}/{IMAGE_MODEL}:generateContent?key={self.api_key}"
        
        # Note: In 2026, Pro Image models use the same 'contents' schema 
        # but return base64 image data in the response parts.
        payload = {
            "contents": [{"parts": [{"text": f"Generate a technical repair diagram: {prompt}"}]}]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=60.0)
            response.raise_for_status()
            return response.json()
