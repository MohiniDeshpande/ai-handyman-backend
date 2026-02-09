import asyncio
import base64
import json
import re

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from app.config import SILENCE_THRESHOLD, AUDIO_TRIGGER_CHUNKS
from app.gemini_client import GeminiClient
from app.session_manager import SessionManager

app = FastAPI()
gemini_client = GeminiClient()
manager = SessionManager()

# Helps when multiple JSON objects get concatenated
JSON_PATTERN = re.compile(r'(\{(?:"type"|"event"):[^}]+\})')

@app.get("/")
def root():
    return {"ok": True, "service": "handybot-ws"}

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    session = manager.get_or_create()
    print(f">>> [WS CONNECTED] session={session.session_id}")

    try:
        while True:
            msg = await ws.receive()
            raw = ""
            if "text" in msg and msg["text"]:
                raw = msg["text"]
            elif "bytes" in msg and msg["bytes"]:
                raw = msg["bytes"].decode("utf-8", errors="ignore")

            if not raw:
                continue

            # Extract possibly concatenated json objects
            objects = JSON_PATTERN.findall(raw) or [raw]
            for obj_str in objects:
                try:
                    data = json.loads(obj_str.strip())
                except:
                    continue

                msg_type = data.get("event") or data.get("type")
                payload = data.get("data") or data.get("value")

                if msg_type == "ping":
                    await ws.send_text(json.dumps({"type": "pong", "event": "pong"}))
                    continue

                if msg_type == "start_capture":
                    session.audio_buffer = []
                    session.is_recording = True
                    continue

                if msg_type == "stop_capture":
                    session.is_recording = False
                    asyncio.create_task(process_ai_request(ws, session))
                    continue

                # Video is continuous
                if msg_type in ["video_b64", "video"]:
                    session.latest_video = payload
                    continue

                # Audio buffers only if loud enough OR "recording" held
                if msg_type in ["audio_b64", "audio"]:
                    if not payload:
                        continue
                    try:
                        audio_bytes = base64.b64decode(payload)
                        audio_data = np.frombuffer(audio_bytes, dtype=np.int16)
                        loud = (np.abs(audio_data).mean() > SILENCE_THRESHOLD)

                        if loud or session.is_recording:
                            session.audio_buffer.append(payload)

                        if len(session.audio_buffer) >= AUDIO_TRIGGER_CHUNKS:
                            asyncio.create_task(process_ai_request(ws, session))
                    except Exception as e:
                        print(f">>> [AUDIO DECODE ERROR] {e}")
                        continue

    except WebSocketDisconnect:
        print(f">>> [WS DISCONNECT] session={session.session_id}")
    except Exception as e:
        print(f">>> [WS ERROR] session={session.session_id} err={e}")
    finally:
        manager.remove(session.session_id)

async def process_ai_request(ws: WebSocket, session):
    if session.processing:
        return
    if not session.audio_buffer:
        return

    session.processing = True
    try:
        current_audio = list(session.audio_buffer)
        current_video = session.latest_video
        session.audio_buffer = []

        # 1) Text tutor response
        ai_text = await gemini_client.analyze_handyman_context(current_audio, current_video)
        if not ai_text:
            return

        # 2) Optional image request (triggered by model line)
        img_req = gemini_client.extract_image_request(ai_text)
        spoken_text = gemini_client.strip_image_request_line(ai_text)

        response_payload = {
            "event": "ai_result",
            "type": "ai_result",
            "data": {
                "speech_text": spoken_text
            }
        }

        # If image requested, generate + attach
        if img_req:
            print(f">>> [IMG REQUEST] {img_req[:80]}")
            img = await gemini_client.generate_reference_image_b64_jpeg(img_req, max_side_px=512, jpeg_quality=70)
            if img:
                mime, b64 = img
                response_payload["data"]["generated_image"] = {
                    "mime_type": mime,
                    "data_b64": b64
                }
                print(f">>> [IMG READY] mime={mime} b64Len={len(b64)}")
            else:
                print(">>> [IMG FAIL] No image returned")

        await ws.send_text(json.dumps(response_payload))
        print(f">>> [AI SENT] {spoken_text[:60]}...")

    except Exception as e:
        print(f">>> [AI TASK ERROR] {e}")
    finally:
        session.processing = False
