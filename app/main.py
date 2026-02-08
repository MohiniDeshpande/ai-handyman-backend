import json, asyncio, logging, base64
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from app.gemini_client import GeminiClient
from app.session_manager import SessionManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("HandymanBridge")

app = FastAPI()
gemini = GeminiClient()
manager = SessionManager()

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    session_id = str(id(ws))
    session = manager.get_or_create(session_id)
    logger.info(f"CONNECTED: {session_id}")

    try:
        while True:
            # Receive raw text from Spectacles
            raw_text = await ws.receive_text()
            
            try:
                # If this fails because of a fragment, the 'except' block will catch it
                data = json.loads(raw_text)
                msg_type = data.get("type")

                if msg_type == "audio":
                    session.add_audio(data.get("value"))
                    if len(session.audio_buffer) % 10 == 0:
                        logger.info(f"Audio received: {len(session.audio_buffer)} chunks")
                
                elif msg_type == "image":
                    session.set_image(data.get("value"))
                    logger.info("Image received")

                # TRIGGER: 1000ms (approx 25 chunks of 40ms audio)
                if len(session.audio_buffer) >= 25:
                    logger.info(">>> THRESHOLD MET: Calling Gemini 3 Pro...")
                    
                    audio_payload = session.get_audio_payload()
                    image_payload = session.get_image_payload()

                    # Gemini 3 Call
                    response = await gemini.ask_foreman(audio_payload, image_payload, session.history)
                    
                    # Send response back to glasses
                    await ws.send_json({
                        "event": "ai_result",
                        "data": {"speech_text": response}
                    })
                    
                    session.clear_audio() # Reset buffer for next turn

            except json.JSONDecodeError:
                # We skip fragments silently to keep the connection alive
                continue

    except WebSocketDisconnect:
        logger.info(f"DISCONNECTED: {session_id}")
    finally:
        manager.delete_session(session_id)
