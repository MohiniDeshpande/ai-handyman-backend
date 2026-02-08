import json, asyncio, logging
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
    
    logger.info(f"==> Session Started: {session_id}")

    try:
        while True:
            # 1. Listen for the Spectacles JSON stream
            data = await ws.receive_json()
            session.add_data(data)

            # 2. If the buffer is full, ask Gemini
            if session.is_ready_to_ask():
                audio_bytes, image_bytes = session.get_multimodal_payload()
                
                # Gemini 3 Pro reasoning
                full_response = await gemini.ask_foreman(
                    audio_bytes, 
                    image_bytes, 
                    session.history
                )

                # 3. Split the response to bypass the 400-char TTS limit
                chunks = session.prepare_chunks_for_spectacles(full_response)
                
                for i, text_chunk in enumerate(chunks):
                    logger.info(f"Sending Chunk {i+1}: {text_chunk}")
                    await ws.send_json({
                        "event": "ai_result",
                        "data": {
                            "speech_text": text_chunk,
                            "is_final": (i == len(chunks) - 1)
                        }
                    })
                    # Pause 100ms so the glasses can queue the audio properly
                    await asyncio.sleep(0.1)

                # 4. Point 7: Update history for continuity
                session.history.append({"role": "model", "parts": [types.Part.from_text(text=full_response)]})

    except WebSocketDisconnect:
        logger.info(f"==> Disconnected: {session_id}")
    finally:
        manager.delete_session(session_id)
