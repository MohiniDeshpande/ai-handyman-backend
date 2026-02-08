from google import genai
from google.genai import types

class GeminiLiveClient:
    def __init__(self, api_key):
        self.client = genai.Client(api_key=api_key, http_options={'api_version': 'v1alpha'})
        self.session = None

    async def start_session(self, ws_callback):
        """
        Maintains a live connection to Gemini 3 Pro.
        """
        config = {"response_modalities": ["TEXT"]}
        
        async with self.client.aio.live.connect(model="gemini-2.0-flash-exp", config=config) as session:
            self.session = session
            # This loop listens for Gemini's voice/text and sends it to the glasses
            async for message in session.receive():
                if message.text:
                    await ws_callback(message.text)

    async def send_to_gemini(self, audio_chunk_b64, image_b64=None):
        """
        Immediately forwards whatever the glasses see/hear.
        No more waiting for batches!
        """
        if not self.session: return
        
        # Send audio as it arrives (raw bytes)
        await self.session.send(
            input=types.LiveClientContent(
                parts=[types.Part.from_bytes(data=audio_chunk_b64, mime_type="audio/pcm")]
            )
        )
        
        # Send image if available (limit to 1 frame per second to save bandwidth)
        if image_b64:
            await self.session.send(
                input=types.LiveClientContent(
                    parts=[types.Part.from_bytes(data=image_b64, mime_type="image/jpeg")]
                )
            )
