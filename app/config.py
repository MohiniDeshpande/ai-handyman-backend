import os

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TEXT_MODEL = "gemini-3-pro-preview"

# Back to original continuous streaming settings
AUDIO_TRIGGER_CHUNKS = 60  
SILENCE_THRESHOLD = 0.01   
THINKING_LEVEL = "high"
