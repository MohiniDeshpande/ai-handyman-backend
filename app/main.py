import asyncio
import json
from fastapi import FastAPI, WebSocket
from .audio_utils import pcm16_to_base64
from .gemini_client import text_response, image_response
from .router import needs_image
from .session_manager import SessionManager
from .config import SESSION_TIMEOUT_SECONDS, WARNING_BEFORE_CLOSE_SECONDS

app = FastAPI()

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()

    session = SessionManager(
        ws,
        SESSION_TIMEOUT_SECONDS,
        WARNING_BEFORE_CLOSE_SECONDS
    )

    asyncio.create_task(session.monitor())

    conversation = []

    try:
        while True:
            msg = await ws.receive()

            session.touch()

            if msg["type"] == "websocket.receive":
                data = msg.get("bytes") or msg.get("text")

                if isinstance(data, bytes):
                    audio_b64 = pcm16_to_base64(data)
                    conversation.append({
                        "role": "user",
                        "parts": [{
                            "inline_data": {
                                "mime_type": "audio/pcm;rate=16000",
                                "data": audio_b64
                            }
                        }]
                    })

                else:
                    parsed = json.loads(data)
                    user_text = parsed["text"]

                    conversation.append({
                        "role": "user",
                        "parts": [{"text": user_text}]
                    })

                    if needs_image(user_text):
                        result = image_response(conversation)
                    else:
                        result = text_response(conversation)

                    model_reply = result["candidates"][0]["content"]
                    conversation.append(model_reply)

                    await ws.send_json({
                        "type": "model_response",
                        "content": model_reply
                    })

    except Exception as e:
        await ws.close()

