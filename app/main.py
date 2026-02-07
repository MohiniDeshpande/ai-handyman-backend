from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import json
import base64

from .audio_utils import decode_audio_chunk
from .image_utils import decode_video_frame
from .gemini_client import GeminiClient

app = FastAPI()
gemini = GeminiClient()

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()

    try:
        while True:
            msg = await ws.receive_text()
            data = json.loads(msg)

            msg_type = data.get("type")
            payload = data.get("payload", {})
            b64_data = payload.get("data")

            if not msg_type or not b64_data:
                continue

            gemini_parts = []

            if msg_type == "audio":
                pcm_bytes = decode_audio_chunk(b64_data)

                gemini_parts.append({
                    "inline_data": {
                        "mime_type": "audio/pcm",
                        "data": base64.b64encode(pcm_bytes).decode()
                    }
                })

            elif msg_type == "video":
                image_bytes = decode_video_frame(b64_data)

                gemini_parts.append({
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": base64.b64encode(image_bytes).decode()
                    }
                })

            else:
                continue

            response = await gemini.send_multimodal(gemini_parts)
            await ws.send_text(json.dumps(response))

    except WebSocketDisconnect:
        print("Client disconnected")
