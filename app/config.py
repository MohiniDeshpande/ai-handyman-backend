import os

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not set")

# Gemini 3 models
TEXT_MODEL = "gemini-3-pro-preview"
IMAGE_MODEL = "gemini-3-pro-image-preview"

# Audio gate
SILENCE_THRESHOLD = 350
AUDIO_TRIGGER_CHUNKS = 60  # ~ how many chunks before forcing an inference
