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
    session = manager.get_or_create()
    
    try:
        while True:
            # Use direct JSON receiving to avoid regex overhead
            try:
                data = await ws.receive_json()
            except:
                break

            msg_type = data.get("event") or data.get("type")
            payload = data.get("data") or data.get("value")

            # 1. Video update (Always active)
            if msg_type in ["video", "video_b64"]:
                session.latest_video = payload

            # 2. START Button Pressed
            elif msg_type == "start_capture":
                session.reset_audio()
                session.is_recording = True
                print(f">>> [LOG] Recording started: {session.session_id}")

            # 3. Audio Stream (ONLY buffer if button is held)
            elif msg_type in ["audio", "audio_b64"] and session.is_recording:
                session.audio_buffer.append(payload)

            # 4. STOP Button Released (Trigger Gemini 3 Pro)
            elif msg_type == "stop_capture":
                session.is_recording = False
                print(f">>> [LOG] Triggering Gemini for {session.session_id}...")
                
                # Fetch AI response using multimodal data
                ai_text = await gemini_client.analyze_handyman_context(
                    session.audio_buffer, session.latest_video
                )
                
                if ws.client_state.name == "CONNECTED":
                    await ws.send_text(json.dumps({
                        "event": "ai_result", 
                        "data": {"speech_text": ai_text}
                    }))
                
                session.reset_audio()

    except WebSocketDisconnect:
        manager.remove(session.session_id)
