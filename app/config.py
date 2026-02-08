import os

# Your API Key from Render Environment Variables
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Model Selection (STRICT: Gemini 3 Pro Preview)
TEXT_MODEL = "gemini-3-pro-preview"

# --- 2026 LATENCY OPTIMIZATION ---
# "low" minimizes first-token delay to <5s
THINKING_LEVEL = "low" 
# "medium" balances detail (wires/screws) with speed
MEDIA_RESOLUTION = "media_resolution_medium" 

# Audio Settings (PCM16 16kHz)
AUDIO_SAMPLE_RATE = 16000
AUDIO_MIME_TYPE = "audio/pcm"
