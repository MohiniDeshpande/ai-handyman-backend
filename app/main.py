import json
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from app.gemini_client import GeminiClient
from app.session_manager import SessionManager

app = FastAPI()
gemini_client = GeminiClient()
manager = SessionManager()

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    # Use the session to isolate this user's audio/video state
    session = manager.get_or_create()
    
    try:
        while True:
            # receive_json is faster and more reliable than regex scanning
            try:
                data = await ws.receive_json()
            except Exception:
                break

            msg_type = data.get("event") or data.get("type")
            payload = data.get("data") or data.get("value")

            # 1. Update latest video frame (always keep this current)
            if msg_type in ["video", "video_b64"]:
                session.latest_video = payload

            # 2. START PTT (Teammate's button event)
            elif msg_type == "start_capture":
                session.reset_audio()
                session.is_recording = True
                print(f">>> [LOG] PTT Started: {session.session_id}")

            # 3. Audio Stream (Only collect if the button is held)
            elif msg_type in ["audio", "audio_b64"] and session.is_recording:
                session.audio_buffer.append(payload)

            # 4. STOP PTT (Trigger Gemini 3 Pro)
            elif msg_type == "stop_capture":
                session.is_recording = False
                print(f">>> [LOG] Requesting AI Analysis...")
                
                ai_text = await gemini_client.analyze_handyman_context(
                    session.audio_buffer, session.latest_video
                )
                
                # Send response back to glasses
                if ws.client_state.name == "CONNECTED":
                    await ws.send_text(json.dumps({
                        "event": "ai_result", 
                        "data": {"speech_text": ai_text}
                    }))
                session.reset_audio()

    except WebSocketDisconnect:
        manager.remove(session.session_id)
