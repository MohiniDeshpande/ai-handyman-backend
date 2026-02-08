import base64
import logging
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)

    async def analyze_handyman_context(self, audio_chunks: list, image_b64: str = None):
        parts = []

        # 1. AUDIO (MUST COME FIRST FOR PRIORITY)
        # We join the chunks into one larger buffer for better speech recognition
        if audio_chunks:
            combined_audio = b"".join([base64.b64decode(c) for c in audio_chunks])
            parts.append(
                types.Part.from_bytes(
                    data=combined_audio, 
                    # CRITICAL: rate=16000 tells Gemini how to 'hear' Spectacles audio
                    mime_type="audio/pcm;rate=16000" 
                )
            )

        # 2. IMAGE (CONTEXT)
        if image_b64:
            parts.append(
                types.Part.from_bytes(
                    data=base64.b64decode(image_b64), 
                    mime_type="image/jpeg"
                )
            )

        # 3. SYSTEM DIRECTIVE
        directive = (
            "You are a Spectacles AI Handyman. PRIORITY: Listen to the audio. "
            "If the audio is silent or unclear, say: 'I couldn't quite hear that, can you repeat?' "
            "If you hear a question, answer it briefly using the image for context. "
            "DO NOT start your response with 'As a handyman' or 'In the photo'."
        )
        parts.append(types.Part.from_text(text=directive))

        try:
            # We use the 'generate_content' with specific 2026 config
            response = await self.client.aio.models.generate_content(
                model="gemini-3-pro-preview",
                contents=[types.Content(role="user", parts=parts)],
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=1000, # Prevents mid-sentence cutoffs
                    thinking_config=types.ThinkingConfig(
                        include_thoughts=False, # Saves bandwidth for the glasses
                        thinking_level=types.ThinkingLevel.LOW # Faster response
                    )
                )
            )
            return response.text
        except Exception as e:
            logger.error(f">>> [GEMINI ERROR] {e}")
            return "Connection error. Try again."
