import base64
import logging
from google import genai
from google.genai import types
from app.config import GEMINI_API_KEY, TEXT_MODEL

logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self, api_key: str = GEMINI_API_KEY):
        # Initializing the main client
        self.client = genai.Client(api_key=api_key)

    async def analyze_handyman_context(self, audio_list: list, image_b64: str = None):
        """
        Sends multimodal data to Gemini 3 Pro using the 2026 Async SDK patterns.
        """
        parts = []

        # 1. Image Part (Visual context)
        if image_b64:
            image_data = base64.b64decode(image_b64)
            parts.append(
                types.Part.from_bytes(data=image_data, mime_type="image/jpeg")
            )

        # 2. Audio Parts (Voice context)
        for chunk in audio_list:
            audio_data = base64.b64decode(chunk)
            parts.append(
                types.Part.from_bytes(data=audio_data, mime_type="audio/pcm")
            )

        # 3. System Instruction as a Text Part
        parts.append(
            types.Part.from_text(
                text="Role: Expert Handyman. Task: Briefly answer the user's question based on the image provided. Stay safe."
            )
        )

        try:
            # Using the .aio module for the asynchronous generate_content call
            response = await self.client.aio.models.generate_content(
                model=TEXT_MODEL,
                contents=[types.Content(role="user", parts=parts)],
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    # Triggers the Gemini 3 Pro reasoning engine
                    thinking_config=types.ThinkingConfig(
                        thinking_level=types.ThinkingLevel.HIGH
                    )
                )
            )
            return response.text
        except Exception as e:
            logger.error(f">>> [GEMINI SDK ERROR] {e}")
            return f"Error connecting to Gemini 3: {str(e)}"
