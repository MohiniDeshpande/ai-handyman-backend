import requests
from .config import (
    GEMINI_API_KEY,
    GEMINI_BASE_URL,
    TEXT_MODEL,
    IMAGE_MODEL
)

HEADERS = {
    "Content-Type": "application/json"
}

def call_gemini(model: str, contents: list):
    url = f"{GEMINI_BASE_URL}/{model}:generateContent?key={GEMINI_API_KEY}"

    payload = {
        "contents": contents
    }

    response = requests.post(url, headers=HEADERS, json=payload)
    response.raise_for_status()
    return response.json()


def text_response(conversation_parts):
    return call_gemini(TEXT_MODEL, conversation_parts)


def image_response(conversation_parts):
    payload = conversation_parts.copy()
    payload.append({
        "role": "user",
        "parts": [{
            "text": "Generate a realistic JPEG image based on the above context."
        }]
    })

    return call_gemini(IMAGE_MODEL, payload)
