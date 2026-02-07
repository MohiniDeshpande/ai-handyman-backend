import json
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from .session_manager import SessionManager
from .gemini_client import GeminiClient
from .config import SESSION_TIMEOUT_SECONDS, WARNING_BEFORE_CLOSE_SECONDS

app = FastAPI()

# Initialize clients
sessions = SessionManager(timeout_seconds=SESSION_TIMEOUT_SECONDS, warning_seconds=WARNING_BEFORE_CLOSE_SECONDS)
gemini_client = GeminiClient()

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    session_id = sessions.create()
    try:
        while True:
            msg = await ws.receive_text()
            try:
                data = json.loads(msg)
            except json.JSONDecodeError:
                await ws.send_text(json.dumps({"error": "Invalid JSON"}))
                continue

            # handle text messages
            if "text" in data:
                response = gemini_client.send_text(data["text"])
                await ws.send_text(json.dumps({"type": "text", "response": response}))

            # handle audio messages
            elif "audio_b64" in data:
                response = gemini_client.send_audio(data["audio_b64"])
                await ws.send_text(json.dumps({"type": "audio", "response": response}))

            # handle image generation
            elif "image_prompt" in data:
                response = gemini_client.generate_image(data["image_prompt"])
                await ws.send_text(json.dumps({"type": "image", "response": response}))

    except WebSocketDisconnect:
        sessions.remove(session_id)
