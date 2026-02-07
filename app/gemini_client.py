import httpx
import json
from app.config import GEMINI_API_KEY, GEMINI_API_URL, TEXT_MODEL

class GeminiClient:
    def __init__(self, api_key: str = GEMINI_API_KEY):
        self.api_key = api_key
        # Target the 3 Pro Preview model via v1beta
        self.endpoint = f"{GEMINI_API_URL}/models/{TEXT_MODEL}:generateContent?key={self.api_key}"

    async def analyze_handyman_context(self, audio_list: list, image_b64: str = None):
        parts = []

        # 1. Visual Modality
        if image_b64:
            parts.append({
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": image_b64
                }
            })

        # 2. Audio Modalities (PCM 16-bit 16kHz)
        for chunk in audio_list:
            parts.append({
                "inline_data": {
                    "mime_type": "audio/pcm;rate=16000",
                    "data": chunk
                }
            })

        # 3. Reasoning Instructions
        parts.append({
            "text": "Role: Expert AI Handyman. Based on the video frame and audio, provide one direct, safe instruction."
        })

        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "temperature": 0.4,
                "max_output_tokens": 150,
                # Requests Gemini 3 Pro's deep reasoning capability
                "thinking_config": {"thinking_level": "high"}
            }
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.endpoint, 
                    json=payload, 
                    headers={"Content-Type": "application/json"},
                    timeout=45.0
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    print(f">>> [GEMINI 3 PRO ERROR] {response.status_code}: {response.text}", flush=True)
                    return None
            except Exception as e:
                print(f">>> [HTTP EXCEPTION] {str(e)}", flush=True)
                return None
