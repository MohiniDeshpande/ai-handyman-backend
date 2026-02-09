import base64
import logging
from google import genai
from google.genai import types
from app.config import GEMINI_API_KEY, TEXT_MODEL

logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self, api_key: str = GEMINI_API_KEY):
        # Initializing the main client (Powered by Gemini 3 Flash for Web)
        self.client = genai.Client(api_key=api_key)

    async def analyze_handyman_context(self, audio_list: list, image_b64: str = None):
        """
        Processes audio and livefeed. If the user asks for a visual, Fixit 
        will start the response with [GENERATE_IMAGE] for the backend to catch.
        """
        parts = []

        # 1. Image Part (Visual context / Livefeed)
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

        # 3. System Instruction 
        # Added logic to trigger image generation via a text keyword
        instruction = (
            "Role: Expert Handyman named Fixit. Task: Briefly answer the user's question based on the livefeed provided. "
            "Stay safe. Refer to any image data as 'livefeed'. Max 400 characters. "
            "IMPORTANT: If the user asks to 'see' a diagram, a visual aid, or how something looks, "
            "start your response EXACTLY with the prefix '[GENERATE_IMAGE]' followed by a descriptive prompt "
            "for an image generator."
        )
        parts.append(types.Part.from_text(text=instruction))

        try:
            response = await self.client.aio.models.generate_content(
                model=TEXT_MODEL,
                contents=[types.Content(role="user", parts=parts)],
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    thinking_config=types.ThinkingConfig(
                        thinking_level=types.ThinkingLevel.LOW # Optimized for <5s response
                    )
                )
            )
            return response.text
            
        except Exception as e:
            logger.error(f">>> [GEMINI SDK ERROR] {e}")
            return f"Error connecting to Gemini 3: {str(e)}"

    async def generate_visual_aid(self, prompt: str):
        """
        Generates an image using the image_generation tool (Nano Banana).
        This is triggered when analyze_handyman_context returns the [GENERATE_IMAGE] prefix.
        """
        try:
            logger.info(f">>> [IMAGE GEN] Generating: {prompt}")
            # Generating a high-fidelity image based on Fixit's prompt
            response = await self.client.aio.models.generate_image(
                model="nano-banana", # 2026 Image Generation model
                prompt=prompt,
                config=types.GenerateImageConfig(
                    output_mime_type="image/jpeg"
                )
            )
            # Encode back to base64 for Spectacles transmission
            return base64.b64encode(response.image_bytes).decode('utf-8')
            
        except Exception as e:
            logger.error(f">>> [IMAGE GEN ERROR] {e}")
            return None
