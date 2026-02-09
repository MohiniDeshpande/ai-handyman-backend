import base64
import logging
import re
from google import genai
from google.genai import types
from app.config import GEMINI_API_KEY, TEXT_MODEL

logger = logging.getLogger(__name__)

HANDYBOT_SYSTEM = """
You are HandyBot — a calm, expert AI handyman tutor that sees through the user’s camera
and hears through their microphone in real time on smart glasses.

MISSION:
Guide the user safely through home repair tasks step-by-step until completion.

CRITICAL CONSTRAINTS (for TTS output):
- Keep responses under 60 words total.
- Max 3 steps per reply.
- Each step must be one short sentence.
- Use simple words.
- No markdown, no bullets, no emojis, no JSON in the spoken part.

STATE & CONTINUITY:
Maintain state across turns:
- Task
- Current step number
- What user already did
- What you need to see/hear next

Always:
1) Confirm progress in one short line if needed.
2) Give next 1–3 steps.
3) End with one short question.

VISION-FIRST:
Don’t guess what you can’t see.
If view is insufficient, include the keyword VIEW in SPOKEN_TEXT.

SAFETY:
If risk exists, start first sentence with SAFETY and give one safe action first.

STOP:
If user says stop/pause/cancel:
"Stopping now. Say start when you want to continue."

OUTPUT FORMAT (EXACT):
SPOKEN_TEXT:
<plain speech only>

CUES:
<one cue per line>

Cue format:
CUE|<type>|<target>|<params>

Allowed types:
HIGHLIGHT_OBJECT, POINT_ARROW, CHECK_ACTION, REQUEST_VIEW, SAFETY_LOCK, STEP

No coordinates. No JSON.
If no cues:
CUES:
CUE|STEP|none|step=<number>
""".strip()


def _clamp_text(s: str, max_chars: int = 360) -> str:
    """Hard cap to protect Lens Studio TTS + Render bandwidth."""
    s = (s or "").strip()
    if len(s) <= max_chars:
        return s
    cut = s[:max_chars]
    last = max(cut.rfind("."), cut.rfind("?"), cut.rfind("!"))
    if last > 80:
        return cut[: last + 1]
    return cut


def parse_handybot_output(full_text: str) -> dict:
    full_text = (full_text or "").strip()

    spoken = ""
    cues = []

    m_spoken = re.search(r"SPOKEN_TEXT:\s*(.*?)(?:\n\s*\n|\nCUES:|$)", full_text, re.S | re.I)
    m_cues = re.search(r"CUES:\s*(.*)$", full_text, re.S | re.I)

    if m_spoken:
        spoken = m_spoken.group(1).strip()
    else:
        spoken = full_text  # fallback

    if m_cues:
        for line in m_cues.group(1).splitlines():
            line = line.strip()
            if line.startswith("CUE|"):
                cues.append(line)

    spoken = _clamp_text(spoken)

    upper = spoken.upper()
    return {
        "spoken_text": spoken,
        "cues": cues,
        "safety_warning": "SAFETY" in upper,
        "request_better_view": "VIEW" in upper,
        "raw": full_text
    }


class GeminiClient:
    def __init__(self, api_key: str = GEMINI_API_KEY):
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not set")
        self.client = genai.Client(api_key=api_key)

    async def analyze_handyman_context(self, audio_list: list[str], image_b64: str | None = None) -> dict:
        """
        audio_list: list of BASE64 encoded PCM16 chunks at 16kHz
        image_b64: BASE64 encoded JPEG (no data-url prefix)
        Returns dict with spoken_text + cues + flags.
        """
        parts: list[types.Part] = []

        # 1) Image part
        if image_b64:
            try:
                image_bytes = base64.b64decode(image_b64)
                parts.append(types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"))
            except Exception as e:
                logger.warning(f"[Gemini] image decode failed: {e}")

        # 2) Audio parts (include rate!)
        for chunk_b64 in (audio_list or []):
            if not chunk_b64:
                continue
            try:
                audio_bytes = base64.b64decode(chunk_b64)
                parts.append(types.Part.from_bytes(data=audio_bytes, mime_type="audio/pcm;rate=16000"))
            except Exception as e:
                logger.warning(f"[Gemini] audio decode failed: {e}")

        # 3) Tiny “format enforcer” user message (NOT the system prompt)
        parts.append(types.Part.from_text(
            "Follow the required output format exactly. Keep SPOKEN_TEXT under 60 words."
        ))

        try:
            response = await self.client.aio.models.generate_content(
                model=TEXT_MODEL,  # e.g. "models/gemini-3-pro-preview"
                contents=[types.Content(role="user", parts=parts)],
                config=types.GenerateContentConfig(
                    system_instruction=HANDYBOT_SYSTEM,
                    temperature=0.2,
                    max_output_tokens=220,  # keep short for Render + TTS
                    thinking_config=types.ThinkingConfig(
                        thinking_level=types.ThinkingLevel.HIGH
                    )
                )
            )

            text = (response.text or "").strip()
            if not text:
                return {
                    "spoken_text": "I didn’t catch that. Show me the area again and say it once more.",
                    "cues": ["CUE|REQUEST_VIEW|work area|hint=move closer", "CUE|STEP|none|step=0"],
                    "safety_warning": False,
                    "request_better_view": True,
                    "raw": ""
                }

            return parse_handybot_output(text)

        except Exception as e:
            logger.error(f">>> [GEMINI SDK ERROR] {e}")
            return {
                "spoken_text": "I’m having trouble connecting right now. Please try again.",
                "cues": ["CUE|STEP|none|step=0"],
                "safety_warning": False,
                "request_better_view": False,
                "raw": str(e)
            }
