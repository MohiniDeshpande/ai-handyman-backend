import base64
import logging
from google import genai
from google.genai import types
from app.config import GEMINI_API_KEY, TEXT_MODEL, MAX_SPOKEN_CHARS

logger = logging.getLogger(__name__)


class GeminiClient:
    def __init__(self, api_key: str = GEMINI_API_KEY):
        self.client = genai.Client(api_key=api_key)

    async def analyze_handyman_context(self, audio_list: list, image_b64: str = None):
        """
        Gemini 3 Pro multimodal reasoning:
        - Audio + optional image
        - Proactive safety detection
        - Short, TTS-safe output
        """

        parts = []

        # ---- 1. IMAGE (optional) ----
        if image_b64:
            try:
                image_bytes = base64.b64decode(image_b64)
                parts.append(
                    types.Part.from_bytes(
                        data=image_bytes,
                        mime_type="image/jpeg"
                    )
                )
            except Exception as e:
                logger.warning(f"[Gemini] Failed to decode image: {e}")

        # ---- 2. AUDIO (PCM16 chunks) ----
        for chunk in audio_list:
            try:
                audio_bytes = base64.b64decode(chunk)
                parts.append(
                    types.Part.from_bytes(
                        data=audio_bytes,
                        mime_type="audio/pcm"
                    )
                )
            except Exception as e:
                logger.warning(f"[Gemini] Failed to decode audio chunk: {e}")

        # ---- 3. SYSTEM / SAFETY INSTRUCTION ----
        instruction = (
            "You are Fixit, an expert handyman and safety auditor.\n"
            "You see through the user's camera and hear them through audio.\n\n"

            "PRIMARY RULE:\n"
            "If you detect ANY safety risk (electricity, sharp tools, gas, heat, load, instability), "
            "you MUST start your response with the exact token [SAFETY_ALERT].\n\n"

            "When a safety risk exists:\n"
            "- Clearly name the danger.\n"
            "- Give ONE immediate action.\n"
            "- Be direct and serious.\n\n"

            "If NO safety risk exists:\n"
            "- Answer the user's question normally as Fixit.\n"
            "- Give at most 3 short steps.\n"
            "- Keep total response under 60 words.\n\n"

            "If the camera view is insufficient, say VIEW and ask for a better angle.\n"
            "If the user says stop or pause, respond with: "
            "'Stopping now. Say start when you want to continue.'\n\n"

            "Do NOT use markdown, emojis, or bullet symbols.\n"
            "Plain spoken English only."
        )

        parts.append(types.Part.from_text(text=instruction))

        # ---- 4. GEMINI CALL ----
        try:
            response = await self.client.aio.models.generate_content(
                model=TEXT_MODEL,
                contents=[types.Content(role="user", parts=parts)],
                config=types.GenerateContentConfig(
                    temperature=0.1,  # factual + safe
                    max_output_tokens=200,
                    thinking_config=types.ThinkingConfig(
                        thinking_level="low"  # cheaper + faster for Render
                    )
                )
            )

            text = response.text or ""

            # ---- 5. HARD CLAMP FOR LENS STUDIO TTS ----
            if len(text) > MAX_SPOKEN_CHARS:
                text = text[:MAX_SPOKEN_CHARS].rsplit(" ", 1)[0] + "..."

            return text.strip()

        except Exception as e:
            logger.error(f"[Gemini SDK ERROR] {e}")
            return "Sorry, I could not analyze that. Please try again."
