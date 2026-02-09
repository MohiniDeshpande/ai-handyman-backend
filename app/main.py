import json
import asyncio
import re
import base64
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from app.gemini_client import GeminiClient
from app.session_manager import SessionManager
from app.config import SILENCE_THRESHOLD, AUDIO_TRIGGER_CHUNKS

app = FastAPI()
gemini_client = GeminiClient()
manager = SessionManager()
JSON_PATTERN = re.compile(r'(\{(?:"type"|"event"):[^}]+\})')

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    # Unique session for this connection
    session = manager.get_or_create()
    print(f">>> [CONNECTED] Session: {session.session_id}")
    
    try:
        while True:
            try:
                message = await ws.receive()
            except: break

            raw_msg = ""
            if "text" in message: raw_msg = message["text"]
            elif "bytes" in message: raw_msg = message["bytes"].decode('utf-8', errors='ignore')

            if not raw_msg: continue

            found_objects = JSON_PATTERN.findall(raw_msg)
            for obj_str in found_objects:
                try:
                    data = json.loads(obj_str.strip())
                    msg_type = data.get("event") or data.get("type")
                    payload = data.get("data") or data.get("value")

                    # Handle Button Events (For your teammate's UI)
                    if msg_type == "start_capture":
                        session.audio_buffer = []
                        session.is_recording = True
                    elif msg_type == "stop_capture":
                        session.is_recording = False
                        # Force trigger when button released
                        asyncio.create_task(process_ai_request(ws, session))

                    # 1. Video (Saved to session)
                    if msg_type in ["video_b64", "video"]:
                        session.latest_video = payload
                    
                    # 2. Audio (Saved to session)
                    elif msg_type in ["audio_b64", "audio"]:
                        # If teammate hasn't added button yet, we use your volume logic
                        audio_bytes = base64.b64decode(payload)
                        audio_data = np.frombuffer(audio_bytes, dtype=np.int16)
                        
                        # Only buffer if loud enough OR button is pressed
                        if np.abs(audio_data).mean() > SILENCE_THRESHOLD or session.is_recording:
                            session.audio_buffer.append(payload)

                        # Auto-trigger if buffer gets too big
                        if len(session.audio_buffer) >= AUDIO_TRIGGER_CHUNKS:
                            asyncio.create_task(process_ai_request(ws, session))
                except: continue
                
    except WebSocketDisconnect:
        manager.remove(session.session_id)

async def process_ai_request(ws: WebSocket, session):
    if not session.audio_buffer: return
    
    # Snapshot the current data
    current_audio = list(session.audio_buffer)
    current_video = session.latest_video
    session.audio_buffer = [] # Clear immediately to avoid double-trigger
    
    ai_text = await gemini_client.analyze_handyman_context(current_audio, current_video)
    
    if ai_text and ws.client_state.name == "CONNECTED":
        await ws.send_text(json.dumps({
            "event": "ai_result",
            "data": {"speech_text": ai_text}
        }))
