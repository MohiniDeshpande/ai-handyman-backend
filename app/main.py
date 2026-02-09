# app/main.py
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

NEED_IMAGE_RE = re.compile(r"NEED_IMAGE:\s*(.+)", re.IGNORECASE)

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    session = manager.get_or_create()
    print(f">>> [CONNECTED] Session: {session.session_id}")

    try:
        while True:
            message = await ws.receive()

            raw_msg = ""
            if "text" in message and message["text"] is not None:
                raw_msg = message["text"]
            elif "bytes" in message and message["bytes"] is not None:
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

                elif msg_type in ["audio_b64", "audio"]:
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

    except WebSocketDisconnect:
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

        ai_text = await gemini_client.analyze_handyman_context(current_audio, current_video)
        if not ai_text:
            return

        generated_image = None
        m = NEED_IMAGE_RE.search(ai_text)
        if m:
            img_prompt = m.group(1).strip()
            # Remove NEED_IMAGE line from spoken text
            ai_text = NEED_IMAGE_RE.sub("", ai_text).strip()
            generated_image = await gemini_client.generate_tool_image_b64(img_prompt)

        payload = {
            "event": "ai_result",
            "type": "ai_result",
            "data": {
                "speech_text": ai_text,
            },
        }

        if generated_image:
            payload["data"]["generated_image"] = generated_image

        await ws.send_text(json.dumps(payload))

    finally:
        session.processing = False
