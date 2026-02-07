import json
import asyncio
import re
import base64
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from app.gemini_client import GeminiClient
from app.config import SILENCE_THRESHOLD, AUDIO_TRIGGER_CHUNKS

app = FastAPI()
gemini_client = GeminiClient()
# Regex to extract JSON objects from potentially corrupted/concatenated packets
JSON_PATTERN = re.compile(r'(\{(?:"type"|"event"):[^}]+\})')

@app.get("/")
async def health_check():
    return {"status": "Gemini 3 Pro Bridge Online"}

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    print(">>> [CONNECTED] Spectacles 3 Pro Active", flush=True)
    
    latest_video = None
    audio_buffer = []

    try:
        while True:
            message = await ws.receive()
            raw_msg = ""
            if "text" in message: raw_msg = message["text"]
            elif "bytes" in message: raw_msg = message["bytes"].decode('utf-8', errors='ignore')

            if not raw_msg: continue

            # Clean and parse messages
            found_objects = JSON_PATTERN.findall(raw_msg)
            for obj_str in found_objects:
                try:
                    data = json.loads(obj_str.strip())
                    msg_type = data.get("event") or data.get("type")
                    payload = data.get("data") or data.get("value")

                    if msg_type in ["video_b64", "video"]:
                        latest_video = payload
                    
                    elif msg_type in ["audio_b64", "audio"]:
                        # Simple Voice Activity Detection
                        audio_bytes = base64.b64decode(payload)
                        audio_data = np.frombuffer(audio_bytes, dtype=np.int16)
                        if np.abs(audio_data).mean() > SILENCE_THRESHOLD:
                            audio_buffer.append(payload)

                        # Trigger SDK call when we have ~2 seconds of audio
                        if len(audio_buffer) >= AUDIO_TRIGGER_CHUNKS:
                            current_batch = list(audio_buffer)
                            audio_buffer = [] # Reset buffer
                            print(">>> [AI] Voice detected. Reasoning with Gemini 3 Pro...", flush=True)
                            asyncio.create_task(process_ai_request(ws, current_batch, latest_video))

                except: continue
    except WebSocketDisconnect:
        print(">>> [DISCONNECTED]", flush=True)

async def process_ai_request(ws: WebSocket, audio: list, image: str):
    ai_text = await gemini_client.analyze_handyman_context(audio, image)
    if ai_text:
        await ws.send_text(json.dumps({
            "event": "ai_result",
            "data": {"speech_text": ai_text}
        }))
        print(f">>> [AI RESPONSE] {ai_text}", flush=True)
