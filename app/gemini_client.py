import os
import requests

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

TEXT_MODEL = "models/gemini-3-pro-preview"
IMAGE_MODEL = "models/gemini-3-pro-image-preview"

BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


def _call(model: str, contents: list):
    url = f"{BASE_URL}/{model}:generateContent?key={GEMINI_API_KEY}"

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0.4
        }
    }

    resp = requests.post(url, json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()


def call_text_model(conversation):
    return _call(TEXT_MODEL, conversation)


def call_image_model(conversation):
   
    conversation = conversation + [{
        "role": "user",
        "parts": [{"text": "Generate an image based on the above context."}]
    }]
    return _call(IMAGE_MODEL, conversation)
