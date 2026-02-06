import os

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY not set")

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
TEXT_MODEL = "models/gemini-3-pro-preview"
IMAGE_MODEL = "models/gemini-3-pro-image-preview"

AUDIO_SAMPLE_RATE = 16000
AUDIO_MIME_TYPE = "audio/pcm;rate=16000"
AUDIO_FLUSH_MS = 500
