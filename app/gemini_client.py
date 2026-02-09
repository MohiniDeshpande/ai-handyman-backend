import base64
import io
import logging
from typing import Optional, Tuple

from google import genai
from google.genai import types
from PIL import Image

from app.config import GEMINI_API_KEY, TEXT_MODEL, IMAGE_MODEL

logger = logging.getLogger(__name__)

# Condensed system prompt (short + deterministic triggers)
SYSTEM_PROMPT = (
    "You are HandyBot, a safe handyman tutor for smart glasses.\n"
    "Use camera+audio context. Output must be short and TTS-safe.\n\n"
    "RULES:\n"
    "- Max 60 words total.\n"
    "- Max 3 steps. Each step is one short sentence.\n"
    "- If danger, start first line with: SAFETY:\n"
    "- If view unclear, start first line with: VIEW:\n"
    "- End with exactly one question.\n"
    "- If user says stop/pause/cancel: reply only: Stopping now. Say start when you want to continue.\n\n"
    "IMAGE TRIGGER:\n"
    "If the user asks what a tool/part looks like, include a final line exactly:\n"
    "IMAGE_REQUEST: <short visual prompt>\n"
    "Otherwise do not include IMAGE_REQUEST.\n"
)

class GeminiClient:
    def __init__(self, api_key: str = GEMINI_API_KEY):
        self.client = genai.Client(api_key=api_key)

    async def analyze_handyman_context(
        self,
        audio_list_b64: list,
        image_b64: Optional[str] = None
    ) -> str:
        parts = []

        if image_b64:
            try:
                image_bytes = base64.b64decode(image_b64)
                parts.append(types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"))
            except Exception as e:
                logger.warning(f"[GeminiClient] bad image_b64: {e}")

        # audio chunks
        for chunk_b64 in audio_list_b64:
            try:
                audio_bytes = base64.b64decode(chunk_b64)
                # NOTE: Spectacles mic is PCM16. Keep mime_type simple.
                parts.append(types.Part.from_bytes(data=audio_bytes, mime_type="audio/pcm"))
            except Exception as e:
                logger.warning(f"[GeminiClient] bad audio chunk: {e}")

        # Put system prompt as text part (works fine for generate_content)
        parts.append(types.Part.from_text(SYSTEM_PROMPT))

        response = await self.client.aio.models.generate_content(
            model=TEXT_MODEL,
            contents=[types.Content(role="user", parts=parts)],
            config=types.GenerateContentConfig(
                temperature=0.4,
                max_output_tokens=220,
            ),
        )

        return response.text or ""

    def extract_image_request(self, text: str) -> Optional[str]:
        if not text:
            return None
        for line in text.splitlines():
            if line.strip().startswith("IMAGE_REQUEST:"):
                req = line.split("IMAGE_REQUEST:", 1)[1].strip()
                return req if req else None
        return None

    def strip_image_request_line(self, text: str) -> str:
        if not text:
            return ""
        lines = []
        for line in text.splitlines():
            if line.strip().startswith("IMAGE_REQUEST:"):
                continue
            lines.append(line)
        return "\n".join(lines).strip()

    async def generate_reference_image_b64_jpeg(
        self,
        prompt: str,
        max_side_px: int = 512,
        jpeg_quality: int = 70
    ) -> Optional[Tuple[str, str]]:
        """
        Returns (mime_type, data_b64) or None.
        Uses IMAGE_MODEL and compresses output for Render/websocket safety.
        """
        try:
            # Ask for Image modality, then extract inline_data bytes.  [oai_citation:1‡geminibyexample.com](https://geminibyexample.com/005-image-generation/)
            resp = await self.client.aio.models.generate_content(
                model=IMAGE_MODEL,
                contents=[prompt],
                config=types.GenerateContentConfig(
                    response_modalities=["Text", "Image"],
                    temperature=0.7,
                ),
            )

            img_bytes = None
            if resp.candidates and resp.candidates[0].content and resp.candidates[0].content.parts:
                for part in resp.candidates[0].content.parts:
                    if getattr(part, "inline_data", None) is not None:
                        # inline_data.data is bytes in python-genai
                        img_bytes = part.inline_data.data
                        break

            if not img_bytes:
                logger.warning("[GeminiClient] No inline image data returned.")
                return None

            # Downscale + JPEG compress
            pil = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            w, h = pil.size
            scale = min(1.0, float(max_side_px) / float(max(w, h)))
            if scale < 1.0:
                pil = pil.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

            out = io.BytesIO()
            pil.save(out, format="JPEG", quality=jpeg_quality, optimize=True)
            out_bytes = out.getvalue()

            # Safety: keep payload small-ish (< ~700KB base64 ideal)
            b64 = base64.b64encode(out_bytes).decode("ascii")
            return ("image/jpeg", b64)

        except Exception as e:
            logger.error(f"[GeminiClient] image gen error: {e}")
            return None
