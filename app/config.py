import os

# This pulls the key from the Render Environment tab we just set up
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Gemini 3 Pro reasoning models
TEXT_MODEL = "gemini-3-pro-preview"
IMAGE_MODEL = "gemini-3-pro-image-preview"

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

SILENCE_THRESHOLD = 350
AUDIO_TRIGGER_CHUNKS = 20
