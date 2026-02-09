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

# If multiple JSON blobs get concatenated, we try to extract them
JSON_PATTERN = re.compile(r'(\{(?:"type"|"event"):[^}]+\})')


@app.get("/health")
def health():
    return {"status": "ok"}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    session = manager.get_or_create()
    print(f">>> [CONNECTED] session={session.session_id}")

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

            # Sometimes clients accidentally concatenate JSON packets
            objs = JSON_PATTERN.findall(raw) or [raw]

            for obj_str in objs:
                try:
                    data = json.loads(obj_str.strip())
                except Exception:
                    continue

                msg_type = data.get("event") or data.get("type")
                payload = data.get("data") or data.get("value")

                # --- keepalive ---
                if msg_type == "ping":
                    await ws.send_text(json.dumps({"event": "pong"}))
                    continue

                # --- controls (optional, for UI press/hold) ---
                if msg_type == "start_capture":
                    session.audio_buffer = []
                    session.is_recording = True
                    print(f">>> [CAPTURE] START session={session.session_id}")
                    continue

                if msg_type == "stop_capture":
                    session.is_recording = False
                    print(f">>> [CAPTURE] STOP session={session.session_id} chunks={len(session.audio_buffer)}")
                    asyncio.create_task(process_ai_request(ws, session))
                    continue

                # --- video stream (continuous) ---
                if msg_type in ("video_b64", "video"):
                    if isinstance(payload, str) and payload:
                        session.latest_video = payload
                    continue

                # --- audio stream (buffered) ---
                if msg_type in ("audio_b64", "audio"):
                    if not isinstance(payload, str) or not payload:
                        continue

                    # quick logging every so often (optional)
                    # print(f">>> [AUDIO] recv b64Len={len(payload)} recording={session.is_recording}")

                    # energy gate
                    try:
                        audio_bytes = base64.b64decode(payload)
                        audio_data = np.frombuffer(audio_bytes, dtype=np.int16)
                        energy = float(np.abs(audio_data).mean())
                    except Exception:
                        continue

                    if energy > SILENCE_THRESHOLD or session.is_recording:
                        session.audio_buffer.append(payload)

                    # auto trigger
                    if len(session.audio_buffer) >= AUDIO_TRIGGER_CHUNKS:
                        asyncio.create_task(process_ai_request(ws, session))

    except WebSocketDisconnect:
        print(f">>> [DISCONNECTED] session={session.session_id}")
    finally:
        manager.remove(session.session_id)


async def process_ai_request(ws: WebSocket, session):
    # prevent overlapping calls
    if session.processing:
        return
    if not session.audio_buffer:
        return

    session.processing = True

    # snapshot
    audio_list = list(session.audio_buffer)
    image_b64 = session.latest_video
    session.audio_buffer = []

    try:
        print(f">>> [AI] calling Gemini session={session.session_id} audioChunks={len(audio_list)} hasVideo={bool(image_b64)}")

        result = await gemini_client.analyze_handyman_context(audio_list, image_b64)
        spoken = (result.get("spoken_text") or "").strip()
        image_prompt = result.get("image_prompt")

        generated_image = None
        if image_prompt:
            print(f">>> [AI] image requested prompt='{image_prompt[:60]}'")
            generated_image = await gemini_client.generate_visual_aid(image_prompt)
            if generated_image:
                print(f">>> [AI] image ready b64Len={len(generated_image.get('data_b64',''))}")
            else:
                print(">>> [AI] image generation failed (no bytes)")

        payload = {
            "type": "ai_result",
            "event": "ai_result",
            "data": {
                "speech_text": spoken,
            }
        }

        if generated_image:
            payload["data"]["generated_image"] = generated_image

        if ws.client_state.name == "CONNECTED":
            await ws.send_text(json.dumps(payload))
            print(f">>> [AI] sent ai_result spokenLen={len(spoken)}")
    except Exception as e:
        print(f">>> [AI ERROR] {e}")
    finally:
        session.processing = False
