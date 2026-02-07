import os

# =========================
# Gemini API Configuration
# =========================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY not set")

# Base URL MUST NOT include model name (Gemini docs compliant)
GEMINI_BASE_URL = os.getenv(
    "GEMINI_BASE_URL",
    "https://generativelanguage.googleapis.com/v1beta"
)

# Models (passed dynamically in request path)
TEXT_MODEL = "models/gemini-3-pro-preview"
IMAGE_MODEL = "models/gemini-3-pro-image-preview"

# =========================
# Audio Configuration
# =========================

AUDIO_SAMPLE_RATE = 16000
AUDIO_MIME_TYPE = "audio/pcm;rate=16000"

# How often audio chunks are flushed upstream (ms)
AUDIO_FLUSH_MS = 500

# =========================
# Session Configuration
# =========================

SESSION_TIMEOUT_SECONDS = 3600  # 1 hour
WARNING_BEFORE_CLOSE_SECONDS = 60
