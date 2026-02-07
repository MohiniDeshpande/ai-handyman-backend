# gemini_client.py
import json
import requests
from config import GEMINI_API_URL, GEMINI_API_KEY

class GeminiClient:
    def __init__(self):
        self.api_url = GEMINI_API_URL
        self.api_key = GEMINI_API_KEY

    def send_audio(self, conversation: list, audio_b64: str):
        """
        Sends audio to Gemini multi-step API
        """
        payload = {
            "conversation": conversation,
            "audio": {
                "mime_type": "audio/pcm;rate=16000",
                "data": audio_b64
            }
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        response = requests.post(f"{self.api_url}/multi_step", json=payload, headers=headers)
        response.raise_for_status()
        return response.json()

    def send_text_or_image(self, conversation: list, image_b64: str = None):
        """
        Sends text or image input to Gemini multi-step API
        """
        payload = {"conversation": conversation}
        if image_b64:
            payload["image"] = {
                "mime_type": "image/png",
                "data": image_b64
            }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        response = requests.post(f"{self.api_url}/multi_step", json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
