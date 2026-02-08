import base64
from google import genai
from google.genai import types
from app.config import GEMINI_API_KEY, TEXT_MODEL, THINKING_LEVEL, MEDIA_RESOLUTION

class GeminiClient:
    def __init__(self, api_key: str = GEMINI_API_KEY):
        self.client = genai.Client(api_key=api_key)

    async def analyze_handyman_context(self, audio_list: list, image_b64: str = None):
        if not audio_list:
            return "I didn't hear your question. Try again while holding the button."

        parts = []
        # Add User Instructions last for better performance
        parts.append(types.Part.from_text(text="""You are an AR Handyman Expert named fixit. 
        Answer the user's audio question concisely based on what they see. 
        Limit your response to 15 words."""))

        # Add visual context
        if image_b64:
            parts.append(types.Part.from_bytes(
                data=base64.b64decode(image_b64), 
                mime_type="image/jpeg"
            ))

        # Add audio chunks
        for chunk in audio_list:
            parts.append(types.Part.from_bytes(
                data=base64.b64decode(chunk), 
                mime_type="audio/pcm"
            ))

        try:
            print(f">>> [LOG] Gemini API: Request started (Mode: {THINKING_LEVEL})")
            response = await self.client.aio.models.generate_content(
                model=TEXT_MODEL,
                contents=[types.Content(role="user", parts=parts)],
                config=types.GenerateContentConfig(
                    temperature=1.0, # Optimized for Gemini 3
                    thinking_config=types.ThinkingConfig(thinking_level=THINKING_LEVEL),
                    media_resolution=MEDIA_RESOLUTION
                )
            )
            return response.text
        except Exception as e:
            print(f">>> [LOG] Gemini Error: {str(e)}")
            return "Error reaching Gemini."
