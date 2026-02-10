# gemini_client.py (TEXT ONLY)
import base64
import logging
from google import genai
from google.genai import types
from app.config import GEMINI_API_KEY, TEXT_MODEL

logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self, api_key: str = GEMINI_API_KEY):
        self.client = genai.Client(api_key=api_key)

    async def analyze_handyman_context(self, audio_list: list, image_b64: str = None):
        parts = []

        if image_b64:
            try:
                image_data = base64.b64decode(image_b64)
                parts.append(types.Part.from_bytes(data=image_data, mime_type="image/jpeg"))
            except Exception as e:
                logger.error(f"[GEMINI] image decode failed: {e}")

        for chunk in audio_list:
            try:
                audio_data = base64.b64decode(chunk)
                parts.append(types.Part.from_bytes(data=audio_data, mime_type="audio/pcm"))
            except Exception as e:
                logger.error(f"[GEMINI] audio decode failed: {e}")

        instruction = (
            "Role: The Safety Auditor who proactively interrupt the user if it sees a wire that looks live, even if the user didn't ask Is this safe? and a reliable jolly Handyman 'Fixit' teaching DIY . "
            "Task: Be a guide and expert handyman and help fixing things stepwise when asked. Monitor the livefeed for hazards (risky wires, gas leaks, incorrect tool use). "
            "PROACTIVE RULE: If you see a safety risk, you MUST start your response with '[SAFETY_ALERT]'. And answer all questions"
            "Describe the danger concisely and give one immediate action. Step wise answer questions"
            "If there is no immediate danger, answer the user's question normally as Fixit."
        )
        parts.append(types.Part.from_text(text=instruction))

        try:
            response = await self.client.aio.models.generate_content(
                model=TEXT_MODEL,
                contents=[types.Content(role="user", parts=parts)],
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    thinking_config=types.ThinkingConfig(thinking_level="low")
                )
            )
            return response.text
        except Exception as e:
            logger.error(f">>> [GEMINI SDK ERROR] {e}")
            return None
