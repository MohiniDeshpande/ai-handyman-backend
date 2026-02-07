import base64
import logging
from google import genai
from google.genai import types
from app.config import GEMINI_API_KEY, TEXT_MODEL

logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self, api_key: str = GEMINI_API_KEY):
        # The SDK automatically uses the correct v1beta endpoint for Gemini 3
        self.client = genai.Client(api_key=api_key)

    async def analyze_handyman_context(self, audio_list: list, image_b64: str = None):
        """
        Sends multimodal data to Gemini 3 Pro using the official GenAI SDK.
        """
        contents = []

        # 1. Image Part
        if image_b64:
            contents.append(
                types.Part.from_bytes(
                    data=base64.b64decode(image_b64),
                    mime_type="image/jpeg"
                )
            )

        # 2. Audio Parts (Spectacles standard PCM 16k)
        for chunk in audio_list:
            contents.append(
                types.Part.from_bytes(
                    data=base64.b64decode(chunk),
                    mime_type="audio/pcm"
                )
            )

        # 3. Reasoning Instruction
        contents.append(
            types.Part.from_text(
                text="You are a professional Handyman AI. Analyze the image and audio. "
                     "Give a 1-sentence repair tip. Highlight safety risks."
            )
        )

        try:
            # Using the asynchronous client 'aio' to prevent blocking the WebSocket
            response = await self.client.aio.models.generate_content(
                model=TEXT_MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    # High thinking level triggers the Gemini 3 deep reasoning
                    thinking_config=types.ThinkingConfig(
                        thinking_level=types.ThinkingLevel.HIGH
                    )
                )
            )
            return response.text
        except Exception as e:
            print(f">>> [SDK ERROR] {e}", flush=True)
            return None
