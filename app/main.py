import json
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from app.gemini_client import GeminiClient
from app.session_manager import SessionManager

app = FastAPI()
gemini_client = GeminiClient()
manager = SessionManager()

@app.get("/")
async def health():
    return {"status": "Handyman API Online", "mode": "Push-to-Talk"}

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    session = manager.get_or_create()
    
    try:
        while True:
            # Handle incoming JSON from Spectacles
            try:
                data = await ws.receive_json()
            except: break

            msg_type = data.get("type") or data.get("event")
            payload = data.get("data")

            # 1. Video Feed (Constant update)
            if msg_type in ["video", "video_b64"]:
                session.latest_video = payload

            # 2. START PTT (User tapped button)
            elif msg_type == "start_capture":
                session.reset_audio()
                session.is_recording = True
                print(f">>> [LOG] Recording started for {session.session_id}")

            # 3. Stream Audio (Only collect if recording is ON)
            # Inside your main.py websocket_endpoint loop
            elif msg_type in ["audio", "audio_b64"]:
                if session.is_recording:
                    session.audio_buffer.append(payload)
                else:
                    # Ignore audio packets sent while the button isn't pressed
                    pass

            # 4. STOP PTT (User released button - Trigger AI)
            elif msg_type == "stop_capture":
                session.is_recording = False
                print(f">>> [LOG] Triggering Gemini 3 Pro for {session.session_id}...")
                
                # Await the response (blocking the loop for this user until finished)
                ai_text = await gemini_client.analyze_handyman_context(
                    session.audio_buffer, session.latest_video
                )
                
                # Send result back in bridge format
                if ws.client_state.name == "CONNECTED":
                    await ws.send_text(json.dumps({
                        "event": "ai_result", 
                        "data": {"speech_text": ai_text}
                    }))
                
                session.reset_audio()

    except WebSocketDisconnect:
        manager.remove(session.session_id)
