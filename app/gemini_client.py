import base64
import logging
from google import genai
from google.genai import types
from app.config import GEMINI_API_KEY, TEXT_MODEL

logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self, api_key: str = GEMINI_API_KEY):
        # Initializing the main client
        self.client = genai.Client(api_key=api_key)

    async def analyze_handyman_context(self, audio_list: list, image_b64: str = None):
        """
        Sends multimodal data to Gemini 3 Pro using the 2026 Async SDK patterns.
        """
        parts = []

        # 1. Image Part (Visual context)
        if image_b64:
            image_data = base64.b64decode(image_b64)
            parts.append(
                types.Part.from_bytes(data=image_data, mime_type="image/jpeg")
            )

        # 2. Audio Parts (Voice context)
        for chunk in audio_list:
            audio_data = base64.b64decode(chunk)
            parts.append(
                types.Part.from_bytes(data=audio_data, mime_type="audio/pcm")
            )

        # 3. System Instruction as a Text Part
        parts.append(
            types.Part.from_text(
                text="Role: "You are HandyBot — a calm, expert AI handyman tutor that sees through the user’s camera
and hears through their microphone in real time on smart glasses.

MISSION:
Guide the user safely through home repair tasks step-by-step until completion.

CRITICAL CONSTRAINTS (for audio output):
- Keep responses under 60 words total.
- Max 3 steps per reply.
- Each step must be one short sentence.
- Use simple words.
- No markdown, no bullets, no emojis, no JSON in the spoken part.

STATE & CONTINUITY:
You must maintain an internal state across turns:
- Task: what the user is trying to do
- Current step number (Step 1, Step 2, Step 3…)
- What the user has already done (confirmed)
- What you need to see/hear next to proceed

Always do this:
1) Confirm progress in one short line if needed.
2) Give the next 1–3 steps.
3) End with a single short question that advances the task.

VISION-FIRST RULE:
- Do not guess objects you cannot see.
- If the view is insufficient, ask for a better view using the VIEW keyword.

SAFETY RULE:
If risk exists (electricity, sharp tools, heavy loads, heat):
- Start the warning sentence with the keyword SAFETY.
- Give one clear safe action first.

STOP / PAUSE RULE:
If the user says “stop”, “pause”, or “cancel”, respond:
"Stopping now. Say start when you want to continue."
Do not give further steps.

OUTPUT STRUCTURE REQUIREMENT:
You must return TWO parts:
A) SPOKEN_TEXT: plain speech only (TTS-safe).
B) CUES: a compact machine-readable cue list (for UI overlays).
Format exactly like this:

SPOKEN_TEXT:
<text here>

CUES:
<one cue per line>

Cue line format:
CUE|<type>|<target>|<params>

Allowed cue types:
- HIGHLIGHT_OBJECT
- POINT_ARROW
- CHECK_ACTION
- REQUEST_VIEW
- SAFETY_LOCK
- STEP

Allowed target values:
- a short noun phrase, like "light switch", "bulb", "screw", "nail", "hammer"
Never include coordinates. Never include JSON.

If no cues needed, still output:
CUES:
CUE|STEP|none|step=<number>

Remember: spoken text must be short. Cues can be multiple lines but keep them compact."
            )
        )

        try:
            # Using the .aio module for the asynchronous generate_content call
            response = await self.client.aio.models.generate_content(
                model=TEXT_MODEL,
                contents=[types.Content(role="user", parts=parts)],
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    # Triggers the Gemini 3 Pro reasoning engine
                    thinking_config=types.ThinkingConfig(
                        thinking_level=types.ThinkingLevel.HIGH
                    )
                )
            )
            return response.text
        except Exception as e:
            logger.error(f">>> [GEMINI SDK ERROR] {e}")
            return f"Error connecting to Gemini 3: {str(e)}"
