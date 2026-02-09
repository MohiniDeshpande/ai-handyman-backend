# config.py (TEXT ONLY)
import os

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not set")

TEXT_MODEL = "gemini-3-pro-preview"

SILENCE_THRESHOLD = 350
AUDIO_TRIGGER_CHUNKS = 40
MAX_SPOKEN_CHARS = 280
