# app/gemini_client.py
import base64
import logging
import re
from io import BytesIO

from google import genai
from google.genai import types

from app.config import (
    GEMINI_API_KEY,
    TEXT_MODEL,
    IMAGE_MODEL,
    THINKING_LEVEL,
    IMAGE_MAX_DIM,
    IMAGE_JPEG_QUALITY,
    IMAGE_MAX_B64_LEN,
)

logger = logging.getLogger(__name__)

GEN_IMAGE_RE = re.compile(r"^\s*GEN_IMAGE:\s*(.+)\s*$", re.IGNORECASE | re.MULTILINE)

SYSTEM_PROMPT = (
    "You are HandyBot, a safe handyman tutor for smart glasses.\n"
    "Use camera + audio context. Give max 3 short steps under 60 words total.\n"
    "If danger: begin with 'SAFETY:'. If view unclear: begin with 'VIEW:'. End with ONE question.\n"
    "If user says stop/pause/cancel: reply exactly: 'Stopping now. Say start when you want to continue.'\n\n"
    "OPTIONAL IMAGE:\n"
    "Only when the user asks what a tool/part looks like OR a visual reference would truly help,\n"
    "add ONE extra line anywhere in your response:\n"
    "GEN_IMAGE: <very short prompt describing the reference image>\n"
    "Otherwise do not include GEN_IMAGE."
)

class GeminiClient:
    def __init__(self, api_key: str = GEMINI_API_KEY):
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not set")
        self.client = genai.Client(api_key=api_key)

    def extract_image_prompt(self, text: str) -> str | None:
        if not text:
            return None
        m = GEN_IMAGE_RE.search(text)
        if not m:
            return None
        prompt = (m.group(1) or "").strip()
        # Keep prompt short to reduce cost / weird generations
        if len(prompt) > 160:
            prompt = prompt[:160].strip()
        return prompt or None

    def strip_gen_image_line(self, text: str) -> str:
        if not text:
            return ""
        # remove the GEN_IMAGE line from spoken text
        return GEN_IMAGE_RE.sub("", text).strip()

    async def analyze_handyman_context(self, audio_list_b64: list[str], image_b64: str | None = None) -> str:
        parts: list[types.Part] = []

        if image_b64:
            try:
                img_bytes = base64.b64decode(image_b64)
                parts.append(types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"))
            except Exception as e:
                logger.warning(f"[Gemini] image decode failed: {e}")

        for chunk_b64 in audio_list_b64:
            try:
                audio_bytes = base64.b64decode(chunk_b64)
                # keep mime_type simple; sample rate context comes from your pipeline
                parts.append(types.Part.from_bytes(data=audio_bytes, mime_type="audio/pcm"))
            except Exception as e:
                logger.warning(f"[Gemini] audio decode failed: {e}")

        parts.append(types.Part.from_text(text=SYSTEM_PROMPT))

        try:
            response = await self.client.aio.models.generate_content(
                model=TEXT_MODEL,
                contents=[types.Content(role="user", parts=parts)],
                config=types.GenerateContentConfig(
                    temperature=0.6,
                    thinking_config=types.ThinkingConfig(
                        thinking_level=types.ThinkingLevel.HIGH if THINKING_LEVEL == "high" else types.ThinkingLevel.LOW
                    ),
                    max_output_tokens=220,
                ),
            )
            return (response.text or "").strip()
        except Exception as e:
            logger.error(f">>> [GEMINI TEXT ERROR] {e}")
            return "VIEW: I lost connection. Please try again. What are you working on?"

    async def generate_reference_image_b64(self, prompt: str) -> tuple[str, str] | None:
        """
        Returns (mime_type, b64_jpeg)
        """
        if not prompt:
            return None

        try:
            resp = await self.client.aio.models.generate_content(
                model=IMAGE_MODEL,
                contents=[types.Content(role="user", parts=[types.Part.from_text(text=prompt)])],
                config=types.GenerateContentConfig(temperature=0.7),
            )

            # Find inline image bytes
            img_bytes = None
            for cand in (resp.candidates or []):
                content = getattr(cand, "content", None)
                if not content:
                    continue
                for p in (content.parts or []):
                    inline = getattr(p, "inline_data", None) or getattr(p, "inlineData", None)
                    if inline and getattr(inline, "data", None):
                        img_bytes = base64.b64decode(inline.data)
                        break
                if img_bytes:
                    break

            if not img_bytes:
                logger.warning("[Gemini Image] No inline image returned")
                return None

            # Compress / resize to keep payload small
            try:
                from PIL import Image
                im = Image.open(BytesIO(img_bytes)).convert("RGB")
                im.thumbnail((IMAGE_MAX_DIM, IMAGE_MAX_DIM))
                out = BytesIO()
                im.save(out, format="JPEG", quality=IMAGE_JPEG_QUALITY, optimize=True)
                img_bytes = out.getvalue()
            except Exception as e:
                logger.warning(f"[Gemini Image] Pillow compress failed, sending raw bytes: {e}")

            b64 = base64.b64encode(img_bytes).decode("utf-8")

            # Hard clamp if still too large (avoid WS payload issues)
            if len(b64) > IMAGE_MAX_B64_LEN:
                logger.warning(f"[Gemini Image] b64 too large ({len(b64)}), dropping image")
                return None

            return ("image/jpeg", b64)

        except Exception as e:
            logger.error(f">>> [GEMINI IMAGE ERROR] {e}")
            return None
