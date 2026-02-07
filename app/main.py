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

# Background task to cleanup expired sessions
async def session_cleanup_task():
    while True:
        sessions.cleanup()
        await asyncio.sleep(30)  # Run cleanup every 30 seconds

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(session_cleanup_task())

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    session_id = sessions.create()
    try:
        await ws.send_text(json.dumps({"session_id": session_id, "message": "Connected"}))

        while True:
            msg = await ws.receive_text()
            try:
                data = json.loads(msg)
            except json.JSONDecodeError:
                await ws.send_text(json.dumps({"error": "Invalid JSON"}))
                continue

            # -------------------------
            # Text messages
            # -------------------------
            if "text" in data:
                try:
                    response = gemini_client.send_text(data["text"])
                    await ws.send_text(json.dumps({"type": "text", "response": response}))
                except Exception as e:
                    await ws.send_text(json.dumps({"type": "error", "message": str(e)}))

            # -------------------------
            # Audio messages (Base64)
            # -------------------------
            elif "audio_b64" in data:
                try:
                    response = gemini_client.send_audio(data["audio_b64"])
                    await ws.send_text(json.dumps({"type": "audio", "response": response}))
                except Exception as e:
                    await ws.send_text(json.dumps({"type": "error", "message": str(e)}))

            # -------------------------
            # Image generation
            # -------------------------
            elif "image_prompt" in data:
                try:
                    response = gemini_client.generate_image(data["image_prompt"])
                    await ws.send_text(json.dumps({"type": "image", "response": response}))
                except Exception as e:
                    await ws.send_text(json.dumps({"type": "error", "message": str(e)}))

            # Unknown message
            else:
                await ws.send_text(json.dumps({"error": "Unknown message type"}))

    except WebSocketDisconnect:
        sessions.remove(session_id)
        print(f"Session {session_id} disconnected")
    except Exception as e:
        sessions.remove(session_id)
        print(f"Session {session_id} error: {e}")
        await ws.close()
