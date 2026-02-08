from google import genai
from google.genai import types
import os

class GeminiClient:
    def __init__(self):
        self.client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        self.model_id = "gemini-3-pro-preview"

    async def ask_foreman(self, audio_bytes, image_bytes, history):
        # Construct the multimodal parts
        parts = [
            types.Part.from_bytes(data=audio_bytes, mime_type="audio/pcm"),
            types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
            "You are the Foreman, a helpful handyman. Briefly explain what to do."
        ]

        # Gemini 3 Specific Configuration
        config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(
                thinking_level=types.ThinkingLevel.LOW # Fast for AR
            ),
            # media_resolution='low' helps reduce lag from Spectacle frames
            media_resolution=types.MediaResolution.LOW 
        )

        response = self.client.models.generate_content(
            model=self.model_id,
            contents=parts,
            config=config
        )
        
        return response.text
