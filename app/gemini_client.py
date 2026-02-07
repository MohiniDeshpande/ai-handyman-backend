import httpx
from config import GEMINI_API_KEY, GEMINI_BASE_URL, GEMINI_MODEL

class GeminiClient:
    def __init__(self):
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY not set")
        if not GEMINI_BASE_URL:
            raise RuntimeError("GEMINI_BASE_URL not set")

        self.headers = {
            "Authorization": f"Bearer {GEMINI_API_KEY}",
            "Content-Type": "application/json",
        }

    async def send_multimodal(self, parts: list[dict]):
        """
        parts example:
        [
          {"inline_data": {"mime_type": "image/jpeg", "data": "<b64>"}},
          {"inline_data": {"mime_type": "audio/pcm", "data": "<b64>"}}
        ]
        """
        payload = {
            "model": GEMINI_MODEL,
            "contents": [
                {
                    "role": "user",
                    "parts": parts
                }
            ]
        }

        async with httpx.AsyncClient(timeout=None) as client:
            resp = await client.post(
                GEMINI_BASE_URL,
                headers=self.headers,
                json=payload
            )
            resp.raise_for_status()
            return resp.json()

