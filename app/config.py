import os

# Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY not set")

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta"
TEXT_MODEL = "models/gemini-3-pro-preview"           # for text/audio/video processing
IMAGE_MODEL = "models/gemini-3-pro-image-preview"    # only for image generation

# Audio config
AUDIO_SAMPLE_RATE = 16000
AUDIO_MIME_TYPE = "audio/pcm"
AUDIO_FLUSH_MS = 500

# Session config
SESSION_TIMEOUT_SECONDS = 3600
WARNING_BEFORE_CLOSE_SECONDS = 60

# 2026 Specific Settings
THINKING_LEVEL = "high"  # Options: "low" (fast/cheap) or "high" (complex reasoning)
MEDIA_RESOLUTION = "media_resolution_high" # New parameter for 2026 vision tasks
