from google import genai
from google.genai import types

class GeminiClient:
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)

    async def stream_handyman_response(self, ws, audio_list: list, image_b64: str = None):
        """
        Uses Gemini 3 Pro in Streaming Mode with Low Thinking Level 
        to minimize latency for Spectacles.
        """
        parts = []
        
        # 1. AUDIO (The Question)
        for chunk in audio_list:
            parts.append(types.Part.from_bytes(data=base64.b64decode(chunk), mime_type="audio/pcm"))

        # 2. IMAGE (The Context)
        if image_b64:
            parts.append(types.Part.from_bytes(data=base64.b64decode(image_b64), mime_type="image/jpeg"))

        # 3. PROMPT
        parts.append(types.Part.from_text(text="You are an expert handyman. Answer the user's question immediately and briefly based on the image."))

        try:
            # We use generate_content_stream for immediate feedback
            async for chunk in self.client.aio.models.generate_content_stream(
                model="gemini-3-pro-preview",
                contents=[types.Content(role="user", parts=parts)],
                config=types.GenerateContentConfig(
                    # CRITICAL: This reduces the "thinking" time for Gemini 3 Pro
                    thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
                    temperature=0.1
                )
            ):
                if chunk.text:
                    # Forward EACH WORD to spectacles instantly
                    await ws.send_text(json.dumps({
                        "event": "ai_result",
                        "data": {"speech_text": chunk.text}
                    }))
        except Exception as e:
            print(f"Error: {e}")
