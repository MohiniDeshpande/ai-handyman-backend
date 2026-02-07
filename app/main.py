import json
import logging
import time
from typing import Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from .config import LOG_LEVEL
from .gemini_client import GeminiClient
from .session_manager import SessionManager

# ===== Logging =====
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("main")

# ===== App =====
app = FastAPI()
gemini = GeminiClient()
sessions = SessionManager()

# ===== Example tool (multi-step function calling) =====
TOOLS = [
    {
        "function_declarations": [
            {
                "name": "identify_object",
                "description": "Identify an object in an image",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "object_name": {"type": "string"}
                    },
                    "required": ["object_name"]
                }
            }
        ]
    }
]


@app.get("/")
def health():
    return {"status": "ok"}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    session_id = sessions.create()
    logger.info(f"[WS] Connected session={session_id}")

    history = []

    try:
        while True:
            raw = await ws.receive_text()
            logger.info(f"[WS] Received payload size={len(raw)}")

            data: Dict[str, Any] = json.loads(raw)

            response = gemini.generate(
                text=data.get("text"),
                image_b64=data.get("image"),
                audio_b64=data.get("audio"),
                tools=TOOLS,
                history=history
            )

            logger.info("[Gemini] Response received")

            # ===== Handle function calls =====
            candidate = response["candidates"][0]
            content = candidate["content"]

            history.append(content)

            if "parts" in content:
                for part in content["parts"]:
                    if "functionCall" in part:
                        fn = part["functionCall"]
                        logger.info(f"[Gemini] Function call: {fn}")

                        # Example function execution
                        if fn["name"] == "identify_object":
                            result = {
                                "object": fn["args"]["object_name"],
                                "confidence": 0.9
                            }

                            history.append({
                                "role": "tool",
                                "parts": [{
                                    "functionResponse": {
                                        "name": fn["name"],
                                        "response": result
                                    }
                                }]
                            })

                            followup = gemini.generate(history=history)
                            await ws.send_text(json.dumps(followup))
                            continue

            await ws.send_text(json.dumps(response))

    except WebSocketDisconnect:
        logger.info(f"[WS] Disconnected session={session_id}")
    except Exception as e:
        logger.exception("[WS] Fatal error")
    finally:
        sessions.close(session_id)
