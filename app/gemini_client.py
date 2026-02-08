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
                text="""You are a Handyman Assistant on AR glasses named Fixy.
                PRIMARY TASK: Listen to the user's audio request and answer it directly. Do not say 'images' always say 'livefeed' when you want to mention the image data."
                CONTEXTUAL TASK: Use the provided image ONLY if the user asks about something visual (e.g., 'What is this?') or if you need to verify a detail they mentioned.
                If the audio is silent or unclear, tell the user: 'I heard you, but I couldn't catch the question. Are you looking at those frames?'
                Be concise; keep responses under 400 characters for AR display."""
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
