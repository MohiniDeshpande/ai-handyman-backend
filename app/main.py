import json
import asyncio
import logging
import base64
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from app.gemini_client import GeminiClient
from app.session_manager import SessionManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
sessions = SessionManager()
gemini_client = GeminiClient()

# Energy threshold for voice detection (adjust if too sensitive)
SILENCE_THRESHOLD = 300 

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    session_id = sessions.create()
    
    latest_video_frame = None
    audio_accumulator = []
    
    logger.info(f"Session {session_id} Started - Adaptive 'Event' Mode")

    try:
        while True:
            raw_msg = await ws.receive_text()
            
            # --- PACKET REPAIR (Crucial for 100ms frequency) ---
            if "}{" in raw_msg:
                raw_msg = "{" + raw_msg.split("}{")[-1]
            
            try:
                data = json.loads(raw_msg)
            except:
                continue

            # --- ADAPTIVE KEY DETECTION ---
            # Prioritizes 'event' as requested
            msg_type = data.get("event") or data.get("type")
            payload = data.get("data") or data.get("value")

            # Route 1: Video (Every 1500ms)
            if msg_type in ["video", "video_b64", "camera"]:
                latest_video_frame = payload
            
            # Route 2: Audio (Accumulate 100ms chunks into 2s)
            elif msg_type in ["audio", "audio_b64", "voice"]:
                if not payload: continue
                
                # --- SILENCE DETECTION ---
                try:
                    audio_bytes = base64.b64decode(payload)
                    audio_data = np.frombuffer(audio_bytes, dtype=np.int16)
                    if np.abs(audio_data).mean() > SILENCE_THRESHOLD:
                        audio_accumulator.append(payload)
                except Exception as e:
                    logger.error(f"Decode Error: {e}")

                if len(audio_accumulator) >= 20: # 20 chunks = 2 seconds
                    chunks_to_send = list(audio_accumulator)
                    audio_accumulator = []
                    asyncio.create_task(
                        generate_ai_response(ws, chunks_to_send, latest_video_frame)
                    )

            elif msg_type == "ping":
                await ws.send_text(json.dumps({"event": "pong"}))

    except WebSocketDisconnect:
        logger.info(f"Session {session_id} disconnected.")
    finally:
        sessions.remove(session_id)

async def generate_ai_response(ws: WebSocket, audio_list: list, image: str):
    try:
        # Get AI Reasoning
        result = await gemini_client.analyze_handyman_context(audio_list, image)
        if not result: return

        ai_text = result['candidates'][0]['content']['parts'][0].get('text', '')
        
        # --- RETURN BOTH FORMATS (Type & Event) ---
        # This ensures the HandymanBackendBridge.ts always catches the result
        response = {
            "type": "ai_result",
            "event": "ai_result",
            "data": {
                "speech_text": ai_text,
                "safety_warning": "SAFETY" in ai_text.upper(),
                "request_better_view": "VIEW" in ai_text.upper()
            }
        }
        await ws.send_text(json.dumps(response))
        logger.info(f"AI Responded: {ai_text[:40]}...")
    except Exception as e:
        logger.error(f"AI Task Error: {e}")
