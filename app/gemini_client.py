# app/gemini_client.py
import base64
import io
import logging
from PIL import Image

from google import genai
from google.genai import types
from app.config import GEMINI_API_KEY, TEXT_MODEL, IMAGE_MODEL

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Role: A safe handyman tutor. Use camera and audio context. "
    "Give max 3 short steps under 60 words. "
    "If danger: start with 'SAFETY:'. If view unclear: start with 'VIEW:'. "
    "End with one question. "
    "If user asks what a tool/nail looks like, add a line 'NEED_IMAGE: <prompt>'. "
    "Otherwise do not add NEED_IMAGE."
)

class GeminiClient:
    def __init__(self, api_key: str = GEMINI_API_KEY):
        self.client = genai.Client(api_key=api_key)

    async def analyze_handyman_context(self, audio_list: list, image_b64: str | None = None) -> str:
        parts = []

        if image_b64:
            try:
                image_data = base64.b64decode(image_b64)
                parts.append(types.Part.from_bytes(data=image_data, mime_type="image/jpeg"))
            except Exception as e:
                logger.warning(f"[GEMINI] bad image_b64 decode: {e}")

        for chunk in audio_list:
            try:
                audio_data = base64.b64decode(chunk)
                # IMPORTANT: include rate in mime_type for best results
                parts.append(types.Part.from_bytes(data=audio_data, mime_type="audio/pcm;rate=16000"))
            except Exception as e:
                logger.warning(f"[GEMINI] bad audio chunk decode: {e}")

        parts.append(types.Part.from_text(text=SYSTEM_PROMPT))

        try:
            resp = await self.client.aio.models.generate_content(
                model=TEXT_MODEL,
                contents=[types.Content(role="user", parts=parts)],
                config=types.GenerateContentConfig(
                    temperature=0.4
                )
            )
            return resp.text or ""
        except Exception as e:
            logger.error(f">>> [GEMINI TEXT ERROR] {e}")
            return ""

    async def generate_tool_image_b64(self, prompt: str) -> dict | None:
        """
        Calls IMAGE_MODEL, then compresses output to small JPEG for WS.
        Returns: { mime_type: "image/jpeg", data_b64: "<base64>" }
        """
        prompt = (prompt or "").strip()
        if not prompt:
            return None

        try:
            resp = await self.client.aio.models.generate_content(
                model=IMAGE_MODEL,
                contents=[types.Content(role="user", parts=[types.Part.from_text(text=prompt)])],
                config=types.GenerateContentConfig(temperature=0.7),
            )

            # Look for inline image bytes
            img_bytes = None
            cand = (resp.candidates or [None])[0]
            if cand and cand.content and cand.content.parts:
                for p in cand.content.parts:
                    if getattr(p, "inline_data", None) and p.inline_data.data:
                        # p.inline_data.data is base64-ish in some shapes; handle both
                        data = p.inline_data.data
                        if isinstance(data, str):
                            try:
                                img_bytes = base64.b64decode(data)
                            except:
                                img_bytes = None
                        else:
                            img_bytes = data
                        break

            if not img_bytes:
                logger.warning("[GEMINI IMAGE] No image bytes found in response")
                return None

            # Compress to small JPEG for Render/WS safety
            im = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            im.thumbnail((512, 512))

            out = io.BytesIO()
            im.save(out, format="JPEG", quality=70, optimize=True)
            jpeg_bytes = out.getvalue()

            return {
                "mime_type": "image/jpeg",
                "data_b64": base64.b64encode(jpeg_bytes).decode("utf-8"),
            }

        except Exception as e:
            logger.error(f">>> [GEMINI IMAGE ERROR] {e}")
            return None
