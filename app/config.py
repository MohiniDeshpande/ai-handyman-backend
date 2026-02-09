import os

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not set")

TEXT_MODEL = "gemini-3-pro-preview"
IMAGE_MODEL = "gemini-3-pro-image-preview"

# Tune these for Spectacles mic chunks
SILENCE_THRESHOLD = 350
AUDIO_TRIGGER_CHUNKS = 60  # ~ depends on your chunk size

# Safety: keep outbound short for Lens Studio TTS limits
MAX_SPOKEN_CHARS = 280
