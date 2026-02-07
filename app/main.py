import json
import asyncio
import re
import base64
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from app.gemini_client import GeminiClient

app = FastAPI()
gemini_client = GeminiClient()

# This pattern carves out valid JSON objects from the corrupted string jams
JSON_PATTERN = re.compile(r'(\{(?:"type"|"event"):[^}]+\})')
SILENCE_THRESHOLD = 350 # Ignores background noise

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    print(">>> [CONNECTED] Spectacles Link Active", flush=True)
    
    latest_video = None
    audio_buffer = []

    try:
        while True:
            # Receive handles both Text and Binary frames automatically
            message = await ws.receive()
            raw_msg = ""

            if "text" in message:
                raw_msg = message["text"]
            elif "bytes" in message:
                raw_msg = message["bytes"].decode('utf-8', errors='ignore')

            if not raw_msg:
                continue

            # --- DATA CLEANING (Greedy Splitter) ---
            found_objects = JSON_PATTERN.findall(raw_msg)
            
            for obj_str in found_objects:
                try:
                    # Final safety trim to ensure a clean JSON parse
                    clean_json = obj_str.strip()
                    data = json.loads(clean_json)
                    
                    msg_type = data.get("event") or data.get("type")
                    payload = data.get("data") or data.get("value")

                    # Route Video Frames
                    if msg_type in ["video_b64", "video"]:
                        latest_video = payload
                        # Log frame reception without spamming
                        if len(payload) > 500000:
                            print(f">>> [DATA] Large Video Frame Cached ({len(payload)} chars)", flush=True)
                    
                    # Route Audio Chunks
                    elif msg_type in ["audio_b64", "audio"]:
                        # Simple Voice Activity Detection
                        try:
                            audio_bytes = base64.b64decode(payload)
                            audio_data = np.frombuffer(audio_bytes, dtype=np.int16)
                            if np.abs(audio_data).mean() > SILENCE_THRESHOLD:
                                audio_buffer.append(payload)
                        except:
                            pass

                        # Trigger Gemini after 20 chunks (~2 seconds of speech)
                        if len(audio_buffer) >= 20:
                            current_audio_batch = list(audio_buffer)
                            audio_buffer = [] # Reset immediately
                            print(">>> [AI] Voice detected. Requesting Gemini analysis...", flush=True)
                            asyncio.create_task(
                                run_pipeline(ws, current_audio_batch, latest_video)
                            )

                except Exception:
                    # Skip corrupted fragments silently
                    continue

    except WebSocketDisconnect:
        print(">>> [DISCONNECTED] Spectacles link lost.", flush=True)

async def run_pipeline(ws: WebSocket, audio: list, image: str):
    """Processes AI results and sends them back to the Spectacles bridge."""
    try:
        result = await gemini_client.analyze_handyman_context(audio, image)
        if not result:
            return

        # Extract AI response text
        ai_text = result['candidates'][0]['content']['parts'][0].get('text', '')
        
        if ai_text:
            # Matches HandyBackendBridge.ts expectations
            response = {
                "event": "ai_result",
                "type": "ai_result",
                "data": {
                    "speech_text": ai_text,
                    "safety_warning": "SAFETY" in ai_text.upper()
                }
            }
            await ws.send_text(json.dumps(response))
            print(f">>> [AI RESPONSE] {ai_text[:60]}...", flush=True)

    except Exception as e:
        print(f">>> [PIPELINE ERROR] {e}", flush=True)
