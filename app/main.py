import json
import asyncio
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from .audio_utils import prepare_audio_frame
from .image_utils import parse_image_from_json
from .session_manager import SessionManager
from .gemini_client import GeminiClient
from .router import needs_image
from .config import SESSION_TIMEOUT_SECONDS, WARNING_BEFORE_CLOSE_SECONDS

app = FastAPI()
logging.basicConfig(level=logging.INFO)

gemini = GeminiClient()

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    logging.info("[WS] Connection accepted")

    session = SessionManager(ws, SESSION_TIMEOUT_SECONDS, WARNING_BEFORE_CLOSE_SECONDS)
    asyncio.create_task(session.monitor())

    conversation = []

    try:
        while True:
            msg = await ws.receive()
            session.touch()

            if msg["type"] != "websocket.receive":
                continue

            data = msg.get("bytes") or msg.get("text")
            if not data:
                continue

            # Audio PCM bytes
            if isinstance(data, bytes):
                logging.info(f"[WS] Received audio bytes of length {len(data)}")
                b64_audio = prepare_audio_frame(data)
                conversation.append({
                    "role": "user",
                    "parts": [{"inline_data": {"mime_type": "audio/pcm;rate=16000", "data": b64_audio}}]
                })

            # JSON => image or text
            else:
                parsed = json.loads(data)
                if "image" in parsed:
                    logging.info("[WS] Received image JSON")
                    img_bytes = parse_image_from_json(data)
                    conversation.append({
                        "role": "user",
                        "parts": [{"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(img_bytes).decode()}}]
                    })
                elif "text" in parsed:
                    user_text = parsed["text"]
                    logging.info(f"[WS] Received text: {user_text}")
                    conversation.append({"role": "user", "parts": [{"text": user_text}]})
                else:
                    logging.warning("[WS] Unknown payload received")
                    continue

            # Determine if Gemini needs image processing
            if needs_image(conversation[-1].get("parts", [{}])[0].get("text", "")):
                logging.info("[WS] Sending multi-step request to Gemini with image")
                result = await gemini.multi_step_response(conversation)
            else:
                logging.info("[WS] Sending multi-step request to Gemini with text/audio")
                result = await gemini.multi_step_response(conversation)

            model_reply = result["candidates"][0]["content"]
            conversation.append(model_reply)

            await ws.send_json({"type": "model_response", "content": model_reply})
            logging.info("[WS] Sent model response")

    except WebSocketDisconnect:
        logging.info("[WS] Connection closed by client")
    except Exception as e:
        logging.error(f"[WS] Exception: {e}")
        await ws.close()
