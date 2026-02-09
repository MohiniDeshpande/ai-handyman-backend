# main.py (TEXT ONLY)
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

JSON_PATTERN = re.compile(r'(\{(?:"type"|"event"):[^}]+\})')

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    session = manager.get_or_create()
    print(f">>> [CONNECTED] Session: {session.session_id}")

    # Start proactive safety loop
    safety_task = asyncio.create_task(proactive_safety_loop(ws, session))

    try:
        while True:
            message = await ws.receive()

            raw_msg = ""
            if "text" in message and message["text"]:
                raw_msg = message["text"]
            elif "bytes" in message and message["bytes"]:
                raw_msg = message["bytes"].decode("utf-8", errors="ignore")

            if not raw_msg:
                continue

            found_objects = JSON_PATTERN.findall(raw_msg)
            for obj_str in found_objects:
                try:
                    data = json.loads(obj_str.strip())
                except:
                    continue

                msg_type = data.get("event") or data.get("type")
                payload = data.get("data") or data.get("value")

                if msg_type == "ping":
                    await ws.send_text(json.dumps({"event": "pong"}))
                    continue

                if msg_type == "start_capture":
                    session.audio_buffer = []
                    session.is_recording = True
                    continue

                if msg_type == "stop_capture":
                    session.is_recording = False
                    asyncio.create_task(process_ai_request(ws, session))
                    continue

                if msg_type in ["video_b64", "video"]:
                    session.latest_video = payload
                    continue

                if msg_type in ["audio_b64", "audio"]:
                    if not payload:
                        continue
                    try:
                        audio_bytes = base64.b64decode(payload)
                        audio_data = np.frombuffer(audio_bytes, dtype=np.int16)
                        if np.abs(audio_data).mean() > SILENCE_THRESHOLD or session.is_recording:
                            session.audio_buffer.append(payload)

                        if len(session.audio_buffer) >= AUDIO_TRIGGER_CHUNKS:
                            asyncio.create_task(process_ai_request(ws, session))
                    except Exception as e:
                        print(f">>> [AUDIO DECODE ERROR] {e}")
                        continue

    except WebSocketDisconnect:
        pass
    finally:
        safety_task.cancel()
        manager.remove(session.session_id)
        print(f">>> [DISCONNECTED] Session: {session.session_id}")


async def process_ai_request(ws: WebSocket, session):
    if not session.audio_buffer:
        return
    if session.processing:
        return

    session.processing = True
    try:
        current_audio = list(session.audio_buffer)
        current_video = session.latest_video
        session.audio_buffer = []

        ai_text = await gemini_client.analyze_handyman_context(current_audio, current_video)
        if not ai_text:
            return

        if ws.client_state.name == "CONNECTED":
            await ws.send_text(json.dumps({
                "event": "ai_result",
                "data": {"speech_text": ai_text}
            }))
    finally:
        session.processing = False


async def proactive_safety_loop(ws: WebSocket, session):
    # runs periodically; send proactive_warning if model flags it
    while True:
        await asyncio.sleep(4.0)

        if not session.latest_video:
            continue

        try:
            ai_text = await gemini_client.analyze_handyman_context([], session.latest_video)
            if ai_text and "[SAFETY_ALERT]" in ai_text:
                warning = ai_text.replace("[SAFETY_ALERT]", "").strip()
                if ws.client_state.name == "CONNECTED":
                    await ws.send_text(json.dumps({
                        "event": "proactive_warning",
                        "data": {"severity": "CRITICAL", "message": warning}
                    }))
        except Exception as e:
            print(f">>> [SAFETY LOOP ERROR] {e}")
            continue
