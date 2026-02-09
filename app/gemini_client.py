import base64
import logging

from google import genai
from google.genai import types

from app.config import GEMINI_API_KEY, TEXT_MODEL, IMAGE_MODEL

# Render sometimes boots with stale config during deploy.
# This prevents the whole server from crashing.
try:
    from app.config import MAX_SPOKEN_CHARS
except ImportError:
    MAX_SPOKEN_CHARS = 280
logger = logging.getLogger(__name__)

def _clamp_text(s: str, n: int) -> str:
    s = (s or "").strip()
    if len(s) <= n:
        return s
    return s[: n - 3].rstrip() + "..."

def _extract_image_prompt(text: str) -> str | None:
    """
    Looks for a line like:
    IMAGE_PROMPT: some prompt...
    """
    if not text:
        return None
    for line in text.splitlines():
        if line.strip().upper().startswith("IMAGE_PROMPT:"):
            return line.split(":", 1)[1].strip() or None
    return None


class GeminiClient:
    def __init__(self, api_key: str = GEMINI_API_KEY):
        self.client = genai.Client(api_key=api_key)

    async def analyze_handyman_context(self, audio_list: list[str], image_b64: str | None = None) -> dict:
        """
        Returns:
          {
            "spoken_text": "...",
            "image_prompt": "..." | None
          }
        """
        parts: list[types.Part] = []

        # image context (base64 jpeg from Spectacles)
        if image_b64:
            try:
                image_bytes = base64.b64decode(image_b64)
                parts.append(types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"))
            except Exception as e:
                logger.warning(f"[Gemini] image decode failed: {e}")

        # audio chunks (base64 pcm16 from Spectacles)
        for b64chunk in audio_list or []:
            try:
                audio_bytes = base64.b64decode(b64chunk)
                parts.append(types.Part.from_bytes(data=audio_bytes, mime_type="audio/pcm"))
            except Exception as e:
                logger.warning(f"[Gemini] audio decode failed: {e}")

        system = (
            "You are HandyBot, a safe handyman tutor using the user's camera + voice.\n"
            "Output must be SHORT and TTS-friendly.\n"
            f"Rules:\n"
            f"- Max 60 words, simple sentences, no bullets, no emojis.\n"
            f"- If danger: start with 'SAFETY:'. If view unclear: start with 'VIEW:'.\n"
            f"- End with ONE question.\n"
            f"- If the user asks what a tool/part looks like, include a single line:\n"
            f"  IMAGE_PROMPT: <short prompt for image generation>\n"
            f"- Otherwise omit IMAGE_PROMPT.\n"
        )

        parts.append(types.Part.from_text(system))

        try:
            resp = await self.client.aio.models.generate_content(
                model=TEXT_MODEL,
                contents=[types.Content(role="user", parts=parts)],
                config=types.GenerateContentConfig(
                    temperature=0.4,
                    max_output_tokens=220,
                ),
            )
            text = (resp.text or "").strip()
            image_prompt = _extract_image_prompt(text)

            # remove IMAGE_PROMPT line from spoken output
            if image_prompt:
                filtered = []
                for line in text.splitlines():
                    if not line.strip().upper().startswith("IMAGE_PROMPT:"):
                        filtered.append(line)
                text = "\n".join(filtered).strip()

            return {
                "spoken_text": _clamp_text(text, MAX_SPOKEN_CHARS),
                "image_prompt": image_prompt,
            }

        except Exception as e:
            logger.error(f">>> [GEMINI TEXT ERROR] {e}")
            return {
                "spoken_text": "Sorry, I couldn't reach the AI right now. Try again.",
                "image_prompt": None,
            }

    async def generate_visual_aid(self, prompt: str) -> dict | None:
        """
        Returns:
          {"mime_type": "image/jpeg", "data_b64": "..."} or None
        """
        prompt = (prompt or "").strip()
        if not prompt:
            return None

        try:
            resp = await self.client.aio.models.generate_content(
                model=IMAGE_MODEL,
                contents=[types.Content(role="user", parts=[types.Part.from_text(prompt)])],
                config=types.GenerateContentConfig(
                    temperature=0.4,
                    max_output_tokens=1024,
                ),
            )

            # Gemini image responses typically include inline bytes in parts.
            # We'll scan candidate parts for bytes.
            img_bytes = None
            try:
                cand = resp.candidates[0]
                for p in cand.content.parts:
                    # Different SDK builds expose bytes differently; handle common shapes
                    if getattr(p, "inline_data", None) and getattr(p.inline_data, "data", None):
                        img_bytes = p.inline_data.data
                        break
                    if getattr(p, "data", None) and isinstance(p.data, (bytes, bytearray)):
                        img_bytes = bytes(p.data)
                        break
            except Exception:
                pass

            if not img_bytes:
                logger.warning("[Gemini IMG] No image bytes returned")
                return None

            # Optional: compress to small JPEG to survive free Render + websocket size
            img_bytes = self._compress_to_small_jpeg(img_bytes)

            return {
                "mime_type": "image/jpeg",
                "data_b64": base64.b64encode(img_bytes).decode("utf-8"),
            }

        except Exception as e:
            logger.error(f">>> [GEMINI IMG ERROR] {e}")
            return None

    def _compress_to_small_jpeg(self, img_bytes: bytes) -> bytes:
        """
        Best effort shrink. If Pillow isn't installed, just return original bytes.
        """
        try:
            from PIL import Image
            import io

            im = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            # downscale to max width 512
            max_w = 512
            if im.width > max_w:
                h = int(im.height * (max_w / im.width))
                im = im.resize((max_w, h))
            out = io.BytesIO()
            im.save(out, format="JPEG", quality=70, optimize=True)
            return out.getvalue()
        except Exception:
            return img_bytes
