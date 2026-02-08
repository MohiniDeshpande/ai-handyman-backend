import json, asyncio, logging, re
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from app.gemini_client import GeminiClient
from app.session_manager import SessionManager
from google.genai import types

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
    
    logger.info(f"==> Session Started: {session_id}")

    try:
        while True:
            # 1. Receive raw text to prevent the "Extra Data" JSON crash
            raw_payload = await ws.receive_text()
            
            # 2. Use Regex to split concatenated JSON objects (Fixes Point 1)
            fragments = re.findall(r'\{.*?\}', raw_payload, re.DOTALL)
            
            for fragment in fragments:
                try:
                    data = json.loads(fragment)
                    session.add_data(data)
                except json.JSONDecodeError:
                    continue

            # 3. Only trigger Gemini if the manager says we have enough data
            if session.is_ready_to_ask():
                logger.info(">>> Audio buffer ready. Consulting The Foreman...")
                
                audio_bytes, image_bytes = session.get_multimodal_payload()
                
                # Gemini 3 Pro reasoning (Point 5, 7, 8)
                full_response = await gemini.ask_foreman(
                    audio_bytes, 
                    image_bytes, 
                    session.history
                )

                # 4. Split into 400-char chunks for Spectacles TTS (Point 3, 9)
                chunks = session.prepare_chunks_for_spectacles(full_response)
                
                for i, text_chunk in enumerate(chunks):
                    logger.info(f"Sending Chunk {i+1}/{len(chunks)}: {text_chunk[:50]}...")
                    await ws.send_json({
                        "event": "ai_result",
                        "data": {
                            "speech_text": text_chunk,
                            "is_final": (i == len(chunks) - 1)
                        }
                    })
                    # Pause 100ms so the glasses can queue the audio properly
                    await asyncio.sleep(0.1)

                # 5. Update history for continuity (Point 7)
                session.history.append({
                    "role": "model", 
                    "parts": [types.Part.from_text(text=full_response)]
                })

    except WebSocketDisconnect:
        logger.info(f"==> Disconnected: {session_id}")
    except Exception as e:
        logger.error(f"!!! Loop Error: {e}")
    finally:
        manager.delete_session(session_id)
