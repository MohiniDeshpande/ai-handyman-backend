import json
import asyncio
import base64
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from app.gemini_client import GeminiClient
from app.session_manager import SessionManager
from app.config import SILENCE_THRESHOLD, AUDIO_TRIGGER_CHUNKS
from app.image_store import put_image, get_image

app = FastAPI()
gemini_client = GeminiClient()
manager = SessionManager()

@app.get("/health")
async def health():
    return {"status": "ok"}

# Return base64 JSON (easy for Lens Studio Texture.loadBase64)
@app.get("/imgb64/{image_id}")
async def get_img_b64(image_id: str):
    item = get_image(image_id)
    if not item:
        return JSONResponse({"ok": False}, status_code=404)

    img_bytes, mime, _ts = item
    b64 = base64.b64encode(img_bytes).decode("utf-8")
    return {"ok": True, "mime": mime, "b64": b64}

@app.websocket("/ws/spectacles")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    session = manager.get_or_create()
    print(f">>> [CONNECTED] Session: {session.session_id}")

    try:
        while True:
            message = await ws.receive()

            raw = None
            if "text" in message and message["text"] is not None:
                raw = message["text"]
            elif "bytes" in message and message["bytes"] is not None:
                # if someone accidentally sent bytes, ignore safely
                try:
                    raw = message["bytes"].decode("utf-8", errors="ignore")
                except:
                    raw = None

            if not raw:
                continue

            # handle concatenated json from some clients: "}{"
            if "}{ " in raw or "}{" in raw:
                raw = "{" + raw.split("}{")[-1]

            try:
                data = json.loads(raw)
            except:
                continue

            msg_type = data.get("event") or data.get("type")
            payload = data.get("data") or data.get("value")

            if msg_type == "ping":
                await ws.send_text(json.dumps({"type": "pong", "event": "pong"}))
                continue

            # store latest video always
            if msg_type in ["video_b64", "video"]:
                session.latest_video = payload
                continue

            # buffer audio chunks
            if msg_type in ["audio_b64", "audio"]:
                if not payload:
                    continue

                try:
                    audio_bytes = base64.b64decode(payload)
                    audio_data = np.frombuffer(audio_bytes, dtype=np.int16)
                    loud = np.abs(audio_data).mean() > SILENCE_THRESHOLD
                except:
                    loud = True  # if decode fails, still buffer so you can debug

                if loud or session.is_recording:
                    session.audio_buffer.append(payload)

                if len(session.audio_buffer) >= AUDIO_TRIGGER_CHUNKS:
                    asyncio.create_task(process_ai_request(ws, session))
                continue

            # optional controls (safe to ignore if unused)
            if msg_type in ["control", "start_capture"]:
                session.is_recording = True
                session.audio_buffer = []
                continue
            if msg_type in ["stop_capture"]:
                session.is_recording = False
                asyncio.create_task(process_ai_request(ws, session))
                continue

    except WebSocketDisconnect:
        print(f">>> [DISCONNECTED] {session.session_id}")
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

        ai_text = await gemini_client.analyze_handyman_context(current_audio, current_video)
        if not ai_text:
            return

        # Parse IMAGE_REQUEST
        image_prompt = None
        cleaned = []
        for line in ai_text.splitlines():
            l = line.strip()
            if not l:
                continue
            if l.upper().startswith("IMAGE_REQUEST:"):
                image_prompt = l.split(":", 1)[1].strip()
            else:
                cleaned.append(l)

        speech_text = " ".join(cleaned).strip()

        out = {
            "type": "ai_result",
            "event": "ai_result",
            "data": {
                "speech_text": speech_text
            }
        }

        # generate image only if requested
        if image_prompt:
            img_bytes, mime = await gemini_client.generate_reference_image(
                prompt=image_prompt,
                ref_image_b64=current_video
            )
            if img_bytes:
                image_id = put_image(img_bytes, mime or "image/jpeg")
                out["data"]["generated_image_b64_url"] = f"/imgb64/{image_id}"
                out["data"]["generated_image_mime"] = mime or "image/jpeg"

        if ws.client_state.name == "CONNECTED":
            await ws.send_text(json.dumps(out))
            print(f">>> [AI RESULT] {speech_text[:80]}...")

    finally:
        session.processing = False
