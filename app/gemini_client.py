import requests
import json
from typing import Optional
from .config import GEMINI_API_KEY, GEMINI_API_URL, TEXT_MODEL, IMAGE_MODEL, AUDIO_SAMPLE_RATE, AUDIO_MIME_TYPE

class GeminiClient:
    """
    Wrapper for Gemini API supporting text, audio, video input and image output.
    """

    def __init__(self, api_key: str = GEMINI_API_KEY, base_url: str = GEMINI_API_URL):
        self.api_key = api_key
        self.base_url = base_url

    def send_text(self, text: str, model: str = TEXT_MODEL) -> dict:
        url = f"{self.base_url}/models/{model}:generateText"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {"prompt": text}
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()

    def send_audio(self, audio_b64: str, model: str = TEXT_MODEL) -> dict:
        url = f"{self.base_url}/models/{model}:generateText"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "audio": {
                "content": audio_b64,
                "mime_type": AUDIO_MIME_TYPE,
                "sample_rate_hz": AUDIO_SAMPLE_RATE
            }
        }
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()

    def generate_image(self, prompt: str, model: str = IMAGE_MODEL) -> dict:
        url = f"{self.base_url}/models/{model}:generateImage"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {"prompt": prompt}
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
