import asyncio
import json
from fastapi import FastAPI, WebSocket
from .session_manager import SessionManager
from .gemini_client import call_text_model, call_image_model
from .audio_utils import needs_image

app = FastAPI()

SESSION_TIMEOUT_SECONDS = 60
WARNING_BEFORE_CLOSE_SECONDS = 15


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()

    session = SessionManager(
        ws,
        SESSION_TIMEOUT_SECONDS,
        WARNING_BEFORE_CLOSE_SECONDS
    )
    asyncio.create_task(session.monitor())

    # buffers for fusion
    conversation = []
    pending_audio = []
    pending_image = None

    try:
        while True:
            msg = await ws.receive_text()
            session.touch()

            payload = json.loads(msg)
            msg_type = payload.get("type")

            # ---- AUDIO ----
            if msg_type == "audio":
                pending_audio.append({
                    "inline_data": {
                        "mime_type": "audio/pcm;rate=16000",
                        "data": payload["data"]
                    }
                })

            # ---- IMAGE ----
            elif msg_type == "image":
                pending_image = {
                    "inline_data": {
                        "mime_type": payload["mime_type"],
                        "data": payload["data"]
                    }
                }

            # ---- TEXT (flush trigger) ----
            elif msg_type == "text":
                parts = []

                if pending_image:
                    parts.append(pending_image)

                parts.extend(pending_audio)

                parts.append({"text": payload["text"]})

                user_turn = {
                    "role": "user",
                    "parts": parts
                }

                conversation.append(user_turn)

                # routing logic
                if needs_image(payload["text"]):
                    result = call_image_model(conversation)
                else:
                    result = call_text_model(conversation)

                model_reply = result["candidates"][0]["content"]
                conversation.append(model_reply)

                await ws.send_json({
                    "type": "model_response",
                    "content": model_reply
                })

                # reset fusion buffers
                pending_audio = []
                pending_image = None

    except Exception:
        await ws.close()
