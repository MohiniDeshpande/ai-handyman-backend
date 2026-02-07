import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

# Your utility imports
from .audio_utils import pcm16_to_base64, needs_image, image_response, text_response
from .session_manager import SessionManager  # Make sure this exists

# Session constants
SESSION_TIMEOUT_SECONDS = 300
WARNING_BEFORE_CLOSE_SECONDS = 30

# Initialize FastAPI
app = FastAPI()


# --- Your existing routes (if any) ---
@app.get("/")
async def root():
    return {"message": "AI Handyman Backend is running!"}


# --- WebSocket endpoint ---
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    print("WebSocket connection accepted")

    # Start session monitor
    session = SessionManager(
        ws,
        SESSION_TIMEOUT_SECONDS,
        WARNING_BEFORE_CLOSE_SECONDS
    )
    asyncio.create_task(session.monitor())

    conversation = []

    try:
        while True:
            try:
                # Try receiving text first
                data = await ws.receive_text()
                is_bytes = False
            except Exception:
                # If not text, try bytes
                data = await ws.receive_bytes()
                is_bytes = True

            session.touch()  # Update session timer

            # Handle audio bytes
            if is_bytes:
                audio_b64 = pcm16_to_base64(data)
                conversation.append({
                    "role": "user",
                    "parts": [{"inline_data": {"mime_type": "audio/pcm;rate=16000", "data": audio_b64}}]
                })
                # Optional: send acknowledgement to client
                await ws.send_json({"type": "ack", "message": "Audio received"})

            else:
                # Handle text
                parsed = json.loads(data)
                user_text = parsed.get("text", "")

                conversation.append({
                    "role": "user",
                    "parts": [{"text": user_text}]
                })

                # Decide if response is text or image
                if needs_image(user_text):
                    result = image_response(conversation)
                else:
                    result = text_response(conversation)

                model_reply = result["candidates"][0]["content"]
                conversation.append(model_reply)

                # Send back to client
                await ws.send_json({
                    "type": "model_response",
                    "content": model_reply
                })

    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        print("WebSocket error:", e)
    finally:
        await ws.close()
        print("WebSocket connection closed")


# --- Uvicorn entry point ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=10000, reload=True)
import asyncio
import json
from fastapi import FastAPI, WebSocket
from .audio_utils import pcm16_to_base64
from .gemini_client import text_response, image_response
from .router import needs_image
from .session_manager import SessionManager
from .config import SESSION_TIMEOUT_SECONDS, WARNING_BEFORE_CLOSE_SECONDS

app = FastAPI()

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()

    session = SessionManager(
        ws,
        SESSION_TIMEOUT_SECONDS,
        WARNING_BEFORE_CLOSE_SECONDS
    )

    asyncio.create_task(session.monitor())

    conversation = []

    try:
        while True:
            msg = await ws.receive()

            session.touch()

            if msg["type"] == "websocket.receive":
                data = msg.get("bytes") or msg.get("text")

                if isinstance(data, bytes):
                    audio_b64 = pcm16_to_base64(data)
                    conversation.append({
                        "role": "user",
                        "parts": [{
                            "inline_data": {
                                "mime_type": "audio/pcm;rate=16000",
                                "data": audio_b64
                            }
                        }]
                    })

                else:
                    parsed = json.loads(data)
                    user_text = parsed["text"]

                    conversation.append({
                        "role": "user",
                        "parts": [{"text": user_text}]
                    })

                    if needs_image(user_text):
                        result = image_response(conversation)
                    else:
                        result = text_response(conversation)

                    model_reply = result["candidates"][0]["content"]
                    conversation.append(model_reply)

                    await ws.send_json({
                        "type": "model_response",
                        "content": model_reply
                    })

    except Exception as e:
        await ws.close()



