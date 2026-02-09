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

# How often to run proactive safety checks (seconds)
SAFETY_CHECK_INTERVAL = 4.0


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    session = manager.get_or_create()
    print(f">>> [CONNECTED] Session: {session.session_id}")

    # Start background safety task
    safety_task = asyncio.create_task(process_safety_check(ws, session))

    try:
        while True:
            message = await ws.receive()

            raw_msg = ""
            if "text" in message:
                raw_msg = message["text"]
            elif "bytes" in message:
                raw_msg = message["bytes"].decode("utf-8", errors="ignore")

            if not raw_msg:
                continue

            # Handle packet stitching (Lens Studio can concatenate JSON)
            found_objects = JSON_PATTERN.findall(raw_msg)
            for obj_str in found_objects:
                try:
                    data = json.loads(obj_str.strip())
                except:
                    continue

                msg_type = data.get("event") or data.get("type")
                payload = data.get("data") or data.get("value")

                # ---- CONTROL EVENTS ----
                if msg_type == "start_audio":
                    session.audio_buffer = []
                    session.is_recording = True
                    continue

                if msg_type == "stop_audio":
                    session.is_recording = False
                    asyncio.create_task(process_ai_request(ws, session))
                    continue

                # ---- VIDEO ----
                if msg_type in ["video_b64", "video"]:
                    session.latest_video = payload
                    continue

                # ---- AUDIO ----
                if msg_type in ["audio_b64", "audio"]:
                    if not payload:
                        continue

                    try:
                        audio_bytes = base64.b64decode(payload)
                        audio_data = np.frombuffer(audio_bytes, dtype=np.int16)
                    except:
                        continue

                    # Buffer audio only if loud enough OR explicitly recording
                    if np.abs(audio_data).mean() > SILENCE_THRESHOLD or session.is_recording:
                        session.audio_buffer.append(payload)

                    # Auto-trigger when enough audio collected
                    if len(session.audio_buffer) >= AUDIO_TRIGGER_CHUNKS:
                        asyncio.create_task(process_ai_request(ws, session))

                if msg_type == "ping":
                    await ws.send_text(json.dumps({"event": "pong"}))

    except WebSocketDisconnect:
        print(f">>> [DISCONNECTED] Session: {session.session_id}")

    finally:
        safety_task.cancel()
        manager.remove(session.session_id)


# --------------------------------------------------
# AUDIO + VIDEO → MAIN AI RESPONSE
# --------------------------------------------------
async def process_ai_request(ws: WebSocket, session):
    if session.processing:
        return

    if not session.audio_buffer:
        return

    session.processing = True

    current_audio = list(session.audio_buffer)
    current_video = session.latest_video
    session.audio_buffer = []

    ai_text = await gemini_client.analyze_handyman_context(
        current_audio,
        current_video
    )

    session.processing = False

    if not ai_text:
        return

    if ws.client_state.name != "CONNECTED":
        return

    payload = {
        "event": "ai_result",
        "data": {
            "speech_text": ai_text
        }
    }

    await ws.send_text(json.dumps(payload))
    print(">>> [AI RESULT SENT]")


# --------------------------------------------------
# PROACTIVE VIDEO-ONLY SAFETY CHECK
# --------------------------------------------------
async def process_safety_check(ws: WebSocket, session):
    """
    Runs periodically using ONLY video frames.
    Sends proactive warnings if Gemini detects danger.
    """
    while True:
        await asyncio.sleep(SAFETY_CHECK_INTERVAL)

        # Must have a frame to analyze
        if not session.latest_video:
            continue

        # Avoid overlapping Gemini calls
        if session.processing:
            continue

        try:
            ai_text = await gemini_client.analyze_handyman_context(
                audio_list=[],
                image_b64=session.latest_video
            )
        except Exception as e:
            print(f">>> [SAFETY CHECK ERROR] {e}")
            continue

        if not ai_text:
            continue

        if "[SAFETY_ALERT]" in ai_text:
            warning = ai_text.replace("[SAFETY_ALERT]", "").strip()

            payload = {
                "event": "proactive_warning",
                "data": {
                    "severity": "CRITICAL",
                    "message": warning
                }
            }

            if ws.client_state.name == "CONNECTED":
                await ws.send_text(json.dumps(payload))
                print(">>> [PROACTIVE SAFETY ALERT SENT]")
