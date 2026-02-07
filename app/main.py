import json
import asyncio
import logging
import re
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from app.session_manager import SessionManager
from app.gemini_client import GeminiClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
sessions = SessionManager()
gemini_client = GeminiClient()

def repair_json_stream(raw_data: str):
    """
    Fixes the 'Extra data' error by extracting the last complete JSON object 
    if multiple objects are stuck together in the buffer.
    """
    # Find all top-level JSON objects {}
    objs = re.findall(r'\{(?:[^{}]|(?R))*\}', raw_data)
    if objs:
        # We take the most recent one (the last one in the buffer)
        return json.loads(objs[-1])
    return json.loads(raw_data)

async def handle_ai_logic(ws: WebSocket, data: dict, latest_frame: str):
    """Handles the heavy lifting in the background."""
    try:
        # 1. Notify the user the AI is thinking
        await ws.send_text(json.dumps({"type": "status", "message": "Handyman is thinking..."}))

        # 2. Call Gemini 3 Pro
        response = await gemini_client.analyze_multimodal(
            text=data.get("text"),
            audio_b64=data.get("audio_b64"),
            image_b64=latest_frame
        )

        # 3. Extract and send text back
        ai_text = response['candidates'][0]['content']['parts'][0].get('text', 'I heard you but I couldn\'t generate a response.')
        
        await ws.send_text(json.dumps({
            "type": "ai_guidance",
            "text": ai_text
        }))

        # 4. Handle Diagram Generation if needed
        if "diagram" in ai_text.lower():
            img_response = await gemini_client.generate_handyman_visual(ai_text)
            await ws.send_text(json.dumps({
                "type": "repair_diagram",
                "data": img_response
            }))

    except Exception as e:
        logger.error(f"AI Logic Error: {e}")
        await ws.send_text(json.dumps({"type": "error", "message": "The AI handyman ran into a tool issue."}))

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    session_id = sessions.create()
    latest_frame_b64 = None
    
    logger.info(f"New Handyman Session Started: {session_id}")

    try:
        while True:
            raw_msg = await ws.receive_text()
            
            try:
                # Use repair logic to handle the 'Extra data' issue
                data = repair_json_stream(raw_msg)
            except Exception as e:
                logger.warning(f"Skipping malformed packet: {e}")
                continue

            # Update visual context
            if "image_b64" in data:
                latest_frame_b64 = data["image_b64"]

            # Process Voice or Text triggers
            if "audio_b64" in data or "text" in data:
                # We use create_task so we don't block the loop while waiting for Gemini
                asyncio.create_task(handle_ai_logic(ws, data, latest_frame_b64))

    except WebSocketDisconnect:
        logger.info(f"Session {session_id} disconnected.")
    except Exception as e:
        logger.error(f"Unexpected error in session {session_id}: {e}")
    finally:
        sessions.remove(session_id)
