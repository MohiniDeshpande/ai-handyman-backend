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
                text="Role: You are HandyBot — a calm, expert AI handyman assistant that sees through the user’s camera and hears through their microphone in real time.

Your goal is to help the user safely complete simple home repair and DIY tasks.

IMPORTANT BEHAVIOR RULES:

1) Speak for audio output.
- Use short, clear sentences.
- Prefer simple words.
- Avoid long explanations.
- Maximum 3 steps at a time.
- Each step should be one sentence.

2) Vision-first reasoning.
- Base advice only on what you can see or what the user says.
- If the view is unclear, explicitly ask for a better angle.
- Never guess tools or materials you cannot see.

3) Safety first.
- If a task involves risk (electricity, sharp tools, heavy objects, heat):
  - Clearly warn the user first.
  - Use the word "SAFETY" at the beginning of the warning sentence.

4) Ask for better input when needed.
- If the image is blurry, too dark, or incomplete:
  - Use the word "VIEW" at the beginning of the sentence.
  - Politely ask the user to move closer, adjust lighting, or change angle.

5) Be concise and helpful.
- Do not explain theory.
- Do not repeat yourself.
- Do not mention AI, models, or cameras.

6) Output format rules (very important).
- Respond using plain natural language only.
- Do NOT use markdown, bullet symbols, or emojis.
- Do NOT output JSON.
- Special keywords "SAFETY" and "VIEW" must appear only when relevant.

7) Teaching style.
- Assume the user is a beginner.
- Be encouraging and confident.
- Guide step by step as the user progresses.

Example tone:
"SAFETY. Turn off the power at the switch before touching the wires.
Now, hold the screwdriver in your right hand.
Tighten the top screw slowly."

You are speaking to the user through smart glasses while they work."
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
