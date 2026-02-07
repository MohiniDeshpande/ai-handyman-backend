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
# This pattern extracts valid JSON from cluttered or fragmented network packets
JSON_PATTERN = re.compile(r'(\{(?:"type"|"event"):[^}]+\})')

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    print(">>> [CONNECTED] Spectacles 3 Pro Bridge Active", flush=True)
    
    latest_video = None
    audio_buffer = []

    try:
        while True:
            message = await ws.receive()
            raw_msg = ""
            if "text" in message: raw_msg = message["text"]
            elif "bytes" in message: raw_msg = message["bytes"].decode('utf-8', errors='ignore')

            if not raw_msg: continue

            # Step 1: Greedy Splitter - Find valid data in the stream
            found_objects = JSON_PATTERN.findall(raw_msg)
            for obj_str in found_objects:
                try:
                    data = json.loads(obj_str.strip())
                    msg_type = data.get("event") or data.get("type")
                    payload = data.get("data") or data.get("value")

                    if msg_type in ["video_b64", "video"]:
                        latest_video = payload
                    
                    elif msg_type in ["audio_b64", "audio"]:
                        audio_bytes = base64.b64decode(payload)
                        audio_data = np.frombuffer(audio_bytes, dtype=np.int16)
                        # Voice Activity Detection (VAD)
                        if np.abs(audio_data).mean() > SILENCE_THRESHOLD:
                            audio_buffer.append(payload)

                        # Step 2: Trigger Gemini after receiving enough audio
                        if len(audio_buffer) >= AUDIO_TRIGGER_CHUNKS:
                            batch = list(audio_buffer)
                            audio_buffer = [] # Reset buffer immediately
                            print(">>> [AI] Voice detected. Sending to Gemini 3 Pro...", flush=True)
                            asyncio.create_task(run_3pro_pipeline(ws, batch, latest_video))

                except: continue
    except WebSocketDisconnect:
        print(">>> [DISCONNECTED]", flush=True)

async def run_3pro_pipeline(ws: WebSocket, audio: list, image: str):
    # Step 3: Get refined response and send back to glasses
    result = await gemini_client.analyze_handyman_context(audio, image)
    if result and 'candidates' in result:
        ai_text = result['candidates'][0]['content']['parts'][0].get('text', '')
        if ai_text:
            # Matches the format expected by the Spectacles bridge
            await ws.send_text(json.dumps({
                "event": "ai_result",
                "data": {"speech_text": ai_text}
            }))
            print(f">>> [AI 3 PRO SUCCESS] {ai_text[:50]}...", flush=True)
