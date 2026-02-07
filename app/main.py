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
            msg = await ws.receive()
                session.touch()
                
                if msg["type"] == "websocket.receive":
                
                    if "bytes" in msg and msg["bytes"] is not None:
                        # RAW PCM AUDIO (Spectacles mic)
                        audio_b64 = base64.b64encode(msg["bytes"]).decode("utf-8")
                        pending_audio.append({
                            "inline_data": {
                                "mime_type": "audio/pcm;rate=16000",
                                "data": audio_b64
                            }
                        })
                
                    elif "text" in msg and msg["text"] is not None:
                        payload = json.loads(msg["text"])
                        msg_type = payload.get("type")
                
                        if msg_type == "image":
                            pending_image = {
                                "inline_data": {
                                    "mime_type": payload["mime_type"],
                                    "data": payload["data"]
                                }
                            }
                
                        elif msg_type == "text":

            
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

