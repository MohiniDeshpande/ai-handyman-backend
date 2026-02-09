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
    ai_text = await gemini_client.analyze_handyman_context(session.audio_buffer, session.latest_video)
    
    if ai_text:
        # Check if AI triggered an image generation
        if "[GENERATE_IMAGE]" in ai_text:
            clean_prompt = ai_text.replace("[GENERATE_IMAGE]", "").strip()
            image_b64 = await gemini_client.generate_visual_aid(clean_prompt)
            
            payload = {
                "event": "ai_image_result",
                "data": {
                    "explanation": "Here is a visual for you:",
                    "image_b64": image_b64
                }
            }
        else:
            payload = {
                "event": "ai_result",
                "data": {"speech_text": ai_text}
            }
            
        await ws.send_text(json.dumps(payload))
