import json
import asyncio
import re
import base64
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from app.gemini_client import GeminiClient
from app.session_manager import SessionManager
from app.config import SILENCE_THRESHOLD, AUDIO_TRIGGER_CHUNKS

app = FastAPI()
gemini_client = GeminiClient()
manager = SessionManager()

JSON_PATTERN = re.compile(r'(\{.*?\})', re.DOTALL)

async def handle_ws(ws: WebSocket):
    await ws.accept()
    session = manager.get_or_create()
    print(f">>> [CONNECTED] Session: {session.session_id}")

    try:
        while True:
            message = await ws.receive()

            raw_msg = ""
            if message.get("text") is not None:
                raw_msg = message["text"]
            elif message.get("bytes") is not None:
                raw_msg = message["bytes"].decode("utf-8", errors="ignore")

            if not raw_msg:
                continue

            # Sometimes multiple JSON objects get glued together; extract all
            found = JSON_PATTERN.findall(raw_msg)
            for obj_str in found:
                try:
                    data = json.loads(obj_str.strip())
                except:
                    continue

                msg_type = data.get("event") or data.get("type")
                payload = data.get("data") or data.get("value")

                # --- control from Lens ---
                if msg_type in ["start_capture", "control_start"]:
                    session.audio_buffer = []
                    session.is_recording = True
                    continue

                if msg_type in ["stop_capture", "control_stop"]:
                    session.is_recording = False
                    asyncio.create_task(process_ai_request(ws, session))
                    continue

                # --- video (continuous) ---
                if msg_type in ["video_b64", "video"]:
                    session.latest_video = payload
                    continue

                # --- audio (only while pinched OR loud) ---
                if msg_type in ["audio_b64", "audio"]:
                    if not payload:
                        continue

                    try:
                        audio_bytes = base64.b64decode(payload)
                        audio_data = np.frombuffer(audio_bytes, dtype=np.int16)

                        loud = float(np.abs(audio_data).mean()) > SILENCE_THRESHOLD

                        if session.is_recording or loud:
                            session.audio_buffer.append(payload)

                        # optional auto trigger (if user keeps holding)
                        if session.is_recording and len(session.audio_buffer) >= AUDIO_TRIGGER_CHUNKS:
                            asyncio.create_task(process_ai_request(ws, session))

                    except Exception as e:
                        print(f">>> [AUDIO DECODE ERROR] {e}")
                    continue

                # --- ping/pong ---
                if msg_type == "ping":
                    await ws.send_text(json.dumps({"type": "pong"}))
                    continue

    except WebSocketDisconnect:
        print(f">>> [DISCONNECTED] Session: {session.session_id}")
    finally:
        manager.remove(session.session_id)
        try:
            await ws.close()
        except:
            pass

async def process_ai_request(ws: WebSocket, session):
    if session.processing:
        return
    if not session.audio_buffer:
        return

    session.processing = True
    try:
        current_audio = list(session.audio_buffer)
        current_video = session.latest_video
        session.audio_buffer = []  # clear immediately

        ai_text = await gemini_client.analyze_handyman_context(current_audio, current_video)

        if ai_text and ws.client_state.name == "CONNECTED":
            await ws.send_text(json.dumps({
                "type": "ai_result",
                "event": "ai_result",
                "data": {"speech_text": ai_text}
            }))
            print(f">>> [AI SENT] chars={len(ai_text)}")
    except Exception as e:
        print(f">>> [AI TASK ERROR] {e}")
    finally:
        session.processing = False


# ✅ Accept both paths to avoid mismatch
@app.websocket("/ws")
async def ws_root(ws: WebSocket):
    await handle_ws(ws)

@app.websocket("/ws/spectacles")
async def ws_spectacles(ws: WebSocket):
    await handle_ws(ws)
