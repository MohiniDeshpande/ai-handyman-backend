import json, asyncio, logging, re, time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from app.gemini_client import GeminiClient
from app.session_manager import SessionManager
from google.genai import types

# Enhanced Logging Format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("HandymanBridge")

app = FastAPI()
gemini = GeminiClient()
manager = SessionManager()

@app.get("/")
async def health_check():
    logger.info(">>> Render Health Check Received")
    return {"status": "Foreman is active", "timestamp": time.time()}

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    session_id = str(id(ws))
    session = manager.get_or_create(session_id)
    
    logger.info(f"==> [WS OPEN] Session: {session_id}")

    try:
        while True:
            # 1. Receive raw text with a 20s timeout to keep Render happy
            try:
                raw_payload = await asyncio.wait_for(ws.receive_text(), timeout=20.0)
            except asyncio.TimeoutError:
                # Keep-alive ping
                await ws.send_json({"event": "ping", "data": {"ts": time.time()}})
                continue

            # 2. Extract JSON fragments (fixes the 'Extra Data' bug)
            fragments = re.findall(r'\{.*?\}', raw_payload, re.DOTALL)
            
            if not fragments:
                logger.warning(f"Received non-JSON data: {raw_payload[:100]}...")
                continue

            for fragment in fragments:
                try:
                    data = json.loads(fragment)
                    msg_type = data.get("type", "unknown")
                    
                    # LOGGING: Data receipt
                    if msg_type == "audio":
                        logger.info(f"[{session_id}] Audio Chunk Received ({len(data.get('data', ''))} bytes)")
                    elif msg_type == "image":
                        logger.info(f"[{session_id}] Camera Frame Received")
                    
                    session.add_data(data)
                except Exception as e:
                    logger.error(f"Fragment Error: {e}")

            # 3. Check if we should call Gemini
            # ... inside the while True loop after parsing the JSON ...

            if session.is_ready_to_ask():
                # 1. Grab the 1000ms of data
                audio_bytes, image_bytes = session.get_multimodal_payload()
                
                # 2. Immediate feedback to Spectacles (Stops the 'is it working?' anxiety)
                await ws.send_json({"event": "system", "data": {"message": "Foreman is thinking..."}})
            
                # 3. Call Gemini
                full_response = await gemini.ask_foreman(audio_bytes, image_bytes, session.history)
                
                # 4. Clear the buffer so we don't loop the same audio
                session.audio_buffer = [] 
                
                # 5. Send chunks
                for chunk in session.prepare_chunks_for_spectacles(full_response):
                    await ws.send_json({"event": "ai_result", "data": {"speech_text": chunk}})
                    await asyncio.sleep(0.05)
                                # 4. Chunking for Spectacles TTS (400 char limit)
                                chunks = session.prepare_chunks_for_spectacles(full_response)
                                for i, text_chunk in enumerate(chunks):
                                    logger.info(f"[{session_id}] Sending TTS Chunk {i+1}/{len(chunks)}")
                                    await ws.send_json({
                                        "event": "ai_result",
                                        "data": {
                                            "speech_text": text_chunk,
                                            "is_final": (i == len(chunks) - 1)
                                        }
                                    })
                                    await asyncio.sleep(0.1)
            
                                # Update history
                                session.history.append({
                                    "role": "model", 
                                    "parts": [types.Part.from_text(text=full_response)]
                                })
            
                            except Exception as ai_err:
                                logger.error(f"[{session_id}] Gemini Error: {ai_err}")
                                await ws.send_json({"event": "error", "data": str(ai_err)})
            
                except WebSocketDisconnect:
                    logger.info(f"==> [WS CLOSED] Session: {session_id}")
                except Exception as e:
                    logger.error(f"!!! [CRITICAL ERROR] {e}", exc_info=True)
                finally:
                    manager.delete_session(session_id)
            
