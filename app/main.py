# main.py
import os
import json
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from .config import TEXT_MODEL, IMAGE_MODEL, AUDIO_SAMPLE_RATE, AUDIO_MIME_TYPE
from .gemini_client import GeminiClient
from .session_manager import SessionManager  # imported now

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="AI Handyman Backend")

# Gemini client (multi-model)
gemini_client = GeminiClient(
    text_model=TEXT_MODEL,
    image_model=IMAGE_MODEL,
    audio_sample_rate=AUDIO_SAMPLE_RATE,
    audio_mime_type=AUDIO_MIME_TYPE,
)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logging.info("WebSocket connected")
    session = SessionManager(ws=websocket)

    try:
        while session.active:
            msg = await websocket.receive_text()
            try:
                data = json.loads(msg)
            except json.JSONDecodeError:
                logging.error(
                    f"Invalid JSON received (likely concatenated frames). Length={len(msg)}"
                )
                continue

            msg_type = data.get("type")
            if msg_type == "audio":
                b64_audio = data.get("pcm_b64", "")
                if b64_audio:
                    await gemini_client.send_audio(b64_audio)
                    logging.info(f"Processed audio chunk size={len(b64_audio)}")
            elif msg_type == "image":
                b64_image = data.get("image_b64", "")
                if b64_image:
                    await gemini_client.send_image(b64_image)
                    logging.info(f"Processed image size={len(b64_image)}")
            elif msg_type == "text":
                prompt = data.get("prompt", "")
                if prompt:
                    response = await gemini_client.send_text(prompt)
                    await websocket.send_text(json.dumps({"type": "text_response", "response": response}))
            else:
                logging.warning(f"Unknown message type: {msg_type}")

    except WebSocketDisconnect:
        logging.info("WebSocket disconnected")
        await session.close()
    except Exception as e:
        logging.exception("WebSocket fatal error")
        await session.close()
