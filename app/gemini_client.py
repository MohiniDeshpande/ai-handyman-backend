import base64
import logging
from google import genai
from google.genai import types
from app.config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self, api_key: str = GEMINI_API_KEY):
        # Initializing the main client for 2026 async patterns
        self.client = genai.Client(api_key=api_key)

    async def ask_foreman(self, audio_bytes: bytes, image_bytes: bytes, history: list):
        """
        Main Handyman reasoning loop.
        Optimized for Spectacles: Low Latency + Conversational Persona.
        """
        # Point 5: Sequence Parts - Audio FIRST for attention priority
        parts = [types.Part.from_bytes(data=audio_bytes, mime_type="audio/pcm;rate=16000")]
        
        if image_bytes:
            parts.append(types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"))

        # Point 4: Personas and safety logic
        system_instruction = (
            "You are 'The Foreman', a conversational, pun-loving handyman. "
            "Refer to visual input as the 'Live Feed'. "
            "If a question is short, be punchy. Use builder puns (e.g., 'Nailed it!'). "
            "PRIORITY: Check for immediate safety hazards in the Live Feed. "
            "If danger is present (exposed wires, etc.), lead with a warning."
        )

        try:
            # Using the .aio module for the asynchronous call
            response = await self.client.aio.models.generate_content(
                model="gemini-3-pro-preview",
                contents=history + [types.Content(role="user", parts=parts)],
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction, # Optimized 2026 way
                    temperature=1.0, # Fixed: Gemini 3 prefers 1.0 for response speed
                    max_output_tokens=800, # Safety buffer for 400-char chunks
                    # Point 2: LOW thinking level ensures sub-5 second responses
                    thinking_config=types.ThinkingConfig(
                        include_thoughts=False,
                        thinking_level=types.ThinkingLevel.LOW 
                    )
                )
            )
            return response.text
        except Exception as e:
            logger.error(f">>> [GEMINI SDK ERROR] {e}")
            return "Connection error, chief. Let's try that again."

    async def analyze_handyman_context(self, audio_list: list, image_b64: str = None):
        """
        Standalone/Legacy method for quick analysis without full session history.
        """
        parts = []
        if image_b64:
            parts.append(types.Part.from_bytes(data=base64.b64decode(image_b64), mime_type="image/jpeg"))
        
        # Merge audio list into one for cleaner processing
        if audio_list:
            combined_audio = b"".join([base64.b64decode(c) for c in audio_list])
            parts.append(types.Part.from_bytes(data=combined_audio, mime_type="audio/pcm;rate=16000"))

        try:
            response = await self.client.aio.models.generate_content(
                model="gemini-3-pro-preview",
                contents=[types.Content(role="user", parts=parts)],
                config=types.GenerateContentConfig(
                    temperature=1.0,
                    thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW)
                )
            )
            return response.text
        except Exception as e:
            logger.error(f">>> [CONTEXT ERROR] {e}")
            return f"I hit a snag: {str(e)}"
