import json
import asyncio
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from app.gemini_client import GeminiClient
from app.session_manager import SessionManager

# Configure clear logging for debugging packets
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
sessions = SessionManager()
gemini_client = GeminiClient()

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    session_id = sessions.create()
    
    # State tracking
    latest_video_frame = None
    
    logger.info(f"Session {session_id} started. Waiting for bridge data...")

    try:
        while True:
            # Receive raw string from the bridge
            raw_msg = await ws.receive_text()
            
            # --- FIX: PACKET REPAIR ---
            # Handles {"type":"audio"}{"type":"video"} collision
            if "}{" in raw_msg:
                # Take the most recent complete JSON object
                raw_msg = "{" + raw_msg.split("}{")[-1]
            
            try:
                data = json.loads(raw_msg)
            except json.JSONDecodeError:
                continue

            # --- ROUTING ---
            msg_type = data.get("type")

            # 1. Update visual context (sent every 1500ms)
            if msg_type == "video_b64":
                latest_video_frame = data.get("data")
            
            # 2. Process audio and trigger AI (sent every 1000ms)
            elif msg_type == "audio_b64":
                audio_data = data.get("data")
                
                # Run AI in background so we don't block the next packet
                asyncio.create_task(
                    generate_ai_response(ws, audio_data, latest_video_frame)
                )

            # 3. Handle Pings from HandyBackendBridge.ts
            elif msg_type == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))

    except WebSocketDisconnect:
        logger.info(f"Session {session_id} disconnected.")
    except Exception as e:
        logger.error(f"Runtime Error in session {session_id}: {e}")
    finally:
        sessions.remove(session_id)

async def generate_ai_response(ws: WebSocket, audio: str, image: str):
    """Bridge-compatible response generator."""
    if not audio:
        return

    # Call Gemini via our client
    result = await gemini_client.analyze_handyman_context(audio, image)
    
    if result and 'candidates' in result:
        ai_text = result['candidates'][0]['content']['parts'][0].get('text', 'No response.')
        
        # --- OUTPUT: EXACT BRIDGE FORMAT ---
        # Matches HandyBackendBridge.ts expected structure
        payload = {
            "type": "ai_result",
            "data": {
                "speech_text": ai_text,
                "safety_warning": "Safety" in ai_text, 
                "request_better_view": "blurry" in ai_text.lower()
            }
        }
        
        try:
            await ws.send_text(json.dumps(payload))
        except Exception:
