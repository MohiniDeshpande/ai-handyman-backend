import json
import asyncio
import logging
import base64
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

# We use standard print with flush=True because it's harder for Render to buffer
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    print(">>> WS ACCEPTED: Connection established with Spectacles", flush=True)
    
    try:
        while True:
            # 1. Listen for ANY type of message (Text or Bytes)
            message = await ws.receive()
            
            if "text" in message:
                raw_msg = message["text"]
                print(f">>> RECEIVED TEXT: {len(raw_msg)} chars", flush=True)
            elif "bytes" in message:
                raw_msg = message["bytes"].decode('utf-8', errors='ignore')
                print(f">>> RECEIVED BYTES: {len(message['bytes'])} bytes", flush=True)
            else:
                print(f">>> RECEIVED UNKNOWN TYPE: {message.keys()}", flush=True)
                continue

            # 2. Immediate Check: Can we see the raw string?
            # If you don't see this in logs, data isn't reaching the script
            print(f">>> RAW DATA START: {raw_msg[:100]}", flush=True)

            # 3. Packet Repair
            if "}{" in raw_msg:
                raw_msg = "{" + raw_msg.split("}{")[-1]

            try:
                data = json.loads(raw_msg)
                event_type = data.get("event") or data.get("type")
                print(f">>> PARSED EVENT: {event_type}", flush=True)
                
                # Simple Echo back to Spectacles to prove it's working
                await ws.send_text(json.dumps({"event": "ack", "received": event_type}))
                
            except Exception as json_err:
                print(f">>> JSON ERROR: {json_err} | DATA: {raw_msg[:50]}", flush=True)

    except WebSocketDisconnect:
        print(">>> WS DISCONNECT: Spectacles lost connection", flush=True)
    except Exception as e:
        print(f">>> CRITICAL RUNTIME ERROR: {e}", flush=True)
        
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

