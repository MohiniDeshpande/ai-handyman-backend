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

# Energy threshold for voice detection (300 is a good starting point for PCM16)
SILENCE_THRESHOLD = 300 

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    session_id = sessions.create()
    
    latest_video_frame = None
    audio_accumulator = []
    
    logger.info(f"Handyman Session {session_id} Started")

    try:
        while True:
            raw_msg = await ws.receive_text()
            
            # --- PACKET REPAIR (Fixes the "Extra Data" error) ---
            if "}{" in raw_msg:
                raw_msg = "{" + raw_msg.split("}{")[-1]
            
            try:
                data = json.loads(raw_msg)
            except: continue

            msg_type = data.get("type")

            if msg_type == "video_b64":
                latest_video_frame = data.get("data")
            
            elif msg_type == "audio_b64":
                audio_b64 = data.get("data")
                if not audio_b64: continue
                
                # --- SILENCE DETECTION ---
                audio_bytes = base64.b64decode(audio_b64)
                audio_data = np.frombuffer(audio_bytes, dtype=np.int16)
                energy = np.abs(audio_data).mean()

                if energy > SILENCE_THRESHOLD:
                    audio_accumulator.append(audio_b64)

                # Buffer 20 chunks (approx 2 seconds)
                if len(audio_accumulator) >= 20:
                    chunks_to_send = list(audio_accumulator)
                    audio_accumulator = []
                    asyncio.create_task(
                        generate_response(ws, chunks_to_send, latest_video_frame)
                    )

            elif msg_type == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))

    except WebSocketDisconnect:
        logger.info(f"Session {session_id} closed.")
    finally:
        sessions.remove(session_id)

async def generate_response(ws: WebSocket, audio_list: list, image: str):
    result = await gemini_client.analyze_handyman_context(audio_list, image)
    if not result: return

    try:
        ai_text = result['candidates'][0]['content']['parts'][0].get('text', '')
        payload = {
            "type": "ai_result",
            "data": {
                "speech_text": ai_text,
                "safety_warning": "SAFETY" in ai_text.upper(),
                "request_better_view": "VIEW" in ai_text.upper()
            }
        }
        await ws.send_text(json.dumps(payload))
    except Exception as e:
        logger.error(f"Response error: {e}")
