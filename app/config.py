# app/config.py
import os

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

TEXT_MODEL = "gemini-3-pro-preview"
IMAGE_MODEL = "gemini-3-pro-image-preview"

AUDIO_SAMPLE_RATE = 16000
AUDIO_MIME_TYPE = "audio/pcm"
AUDIO_FLUSH_MS = 500

SESSION_TIMEOUT_SECONDS = 3600
WARNING_BEFORE_CLOSE_SECONDS = 60

THINKING_LEVEL = "low"
MEDIA_RESOLUTION = "media_resolution_high"

SILENCE_THRESHOLD = 350
AUDIO_TRIGGER_CHUNKS = 60

# ---- Image safety for Render/WebSocket payload sizes ----
# Keep the returned JPEG small enough to avoid issues.
IMAGE_MAX_DIM = 512          # max width/height
IMAGE_JPEG_QUALITY = 70      # 50-80 recommended
IMAGE_MAX_B64_LEN = 900_000  # ~0.9MB base64 string (safe-ish)
