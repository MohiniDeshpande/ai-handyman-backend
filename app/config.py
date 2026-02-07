import os

# Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY not set")

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
TEXT_MODEL = "models/gemini-3-pro"           # for text/audio/video processing
IMAGE_MODEL = "models/gemini-3-pro-image"    # only for image generation

# Audio config
AUDIO_SAMPLE_RATE = 16000
AUDIO_MIME_TYPE = "audio/pcm;rate=16000"
AUDIO_FLUSH_MS = 500

# Session config
SESSION_TIMEOUT_SECONDS = 3600
WARNING_BEFORE_CLOSE_SECONDS = 60
