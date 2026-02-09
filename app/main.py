import json
import asyncio
import base64
import logging
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from app.gemini_client import GeminiClient
from app.session_manager import SessionManager
from app.config import SILENCE_THRESHOLD, AUDIO_TRIGGER_CHUNKS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("handybot")

app = FastAPI()
gemini_client = GeminiClient()
manager = SessionManager()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.websocket("/ws/spectacles")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    session = manager.get_or_create()

    logger.info(f">>> [CONNECTED] session={session.session_id}")

    # Session state (per WS connection)
    session.latest_video = None          # base64 jpeg (no prefix)
    session.audio_buffer = []            # list[str] base64 pcm
    session.is_recording = False         # pinch-to-talk or button
    session.processing = False           # prevents overlapping Gemini calls

    try:
        while True:
            msg = await ws.receive()

            # We only support JSON TEXT messages from Lens.
            raw = msg.get("text")
            if not raw:
                # If bytes arrive, ignore (or log once). Your Lens code sends JSON, so bytes aren't needed.
                if msg.get("bytes"):
                    logger.debug("[RX] got bytes frame (ignored)")
                continue

            try:
                data = json.loads(raw)
            except Exception:
                # If the client accidentally concatenated JSONs, ignore rather than regex-hack.
                logger.warning(f"[RX] bad JSON (len={len(raw)}), ignoring")
                continue

            msg_type = data.get("event") or data.get("type")
            payload = data.get("data") or data.get("value")

            # ---- keepalive for Render
            if msg_type == "ping":
                await ws.send_text(json.dumps({"type": "pong", "event": "pong"}))
                continue

            # ---- optional handshake
            if msg_type == "hello":
                logger.info("[RX] hello")
                await ws.send_text(json.dumps({"type": "hello_ack", "event": "hello_ack"}))
                continue

            # ---- control from Lens (start/stop)
            if msg_type in ("control", "start_capture"):
                cmd = data.get("command") or "start"
                if cmd == "start" or msg_type == "start_capture":
                    session.is_recording = True
                    session.audio_buffer = []
                    logger.info("[CTRL] start recording")
                continue

            if msg_type in ("stop_capture",):
                session.is_recording = False
                logger.info("[CTRL] stop recording -> trigger")
                # Trigger immediately when user releases pinch/button
                asyncio.create_task(process_ai_request(ws, session))
                continue

            if msg_type == "control":
                cmd = data.get("command")
                if cmd == "stop":
                    session.is_recording = False
                    logger.info("[CTRL] stop streaming")
                continue

            # ---- video frames
            if msg_type in ("video_b64", "video"):
                if isinstance(payload, str) and payload:
                    session.latest_video = payload
                    logger.debug(f"[RX] video_b64 len={len(payload)}")
                continue

            # ---- audio chunks
            if msg_type in ("audio_b64", "audio"):
                if not isinstance(payload, str) or not payload:
                    continue

                # If not recording (no pinch) we still allow your silence trigger mode
                should_buffer = session.is_recording

                if not should_buffer:
                    # loudness check
                    try:
                        audio_bytes = base64.b64decode(payload)
                        audio_i16 = np.frombuffer(audio_bytes, dtype=np.int16)
                        loudness = float(np.abs(audio_i16).mean())
                        should_buffer = loudness > SILENCE_THRESHOLD
                    except Exception as e:
                        logger.warning(f"[AUDIO] decode failed: {e}")
                        should_buffer = False

                if should_buffer:
                    session.audio_buffer.append(payload)
                    logger.debug(f"[RX] audio_b64 chunks={len(session.audio_buffer)}")

                # Auto trigger when buffer reaches threshold
                if len(session.audio_buffer) >= AUDIO_TRIGGER_CHUNKS:
                    logger.info(f"[TRIGGER] chunks={len(session.audio_buffer)} -> process_ai_request")
                    asyncio.create_task(process_ai_request(ws, session))
                continue

            # Unknown messages
            logger.debug(f"[RX] unknown type={msg_type}")

    except WebSocketDisconnect:
        logger.info(f">>> [DISCONNECTED] session={session.session_id}")
    except Exception as e:
        logger.error(f">>> [WS ERROR] session={session.session_id} err={e}")
    finally:
        manager.remove(session.session_id)


async def process_ai_request(ws: WebSocket, session):
    """
    Snapshot current buffers and call Gemini. Returns ai_result with:
    - speech_text (short)
    - cues (list of cue lines)
    - flags
    """
    if session.processing:
        return
    if not session.audio_buffer:
        return

    session.processing = True

    # Snapshot
    current_audio = list(session.audio_buffer)
    current_video = session.latest_video
    session.audio_buffer = []  # clear immediately

    logger.info(f"[AI] request audio_chunks={len(current_audio)} video={'yes' if bool(current_video) else 'no'}")

    try:
        result = await gemini_client.analyze_handyman_context(
            audio_list=current_audio,
            image_b64=current_video
        )
        # result is dict from gemini_client.py
        speech_text = (result.get("spoken_text") or "").strip()
        cues = result.get("cues") or []
        safety = bool(result.get("safety_warning"))
        better = bool(result.get("request_better_view"))

        # Safety: never send huge text back to Lens (protect TTS)
        if len(speech_text) > 500:
            speech_text = speech_text[:500]

        payload = {
            "type": "ai_result",
            "event": "ai_result",
            "data": {
                "speech_text": speech_text,
                "cues": cues,
                "safety_warning": safety,
                "request_better_view": better,
                # optional image generation will go here later:
                # "generated_image": {"mime_type": "...", "data_b64": "..."}
            }
        }

        if ws.client_state.name == "CONNECTED":
            await ws.send_text(json.dumps(payload))
            logger.info(f"[AI] sent ai_result chars={len(speech_text)} cues={len(cues)} safety={safety} view={better}")

    except Exception as e:
        logger.error(f"[AI] error: {e}")
    finally:
        session.processing = False
