import json, asyncio, logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from app.gemini_client import GeminiClient
from app.session_manager import SessionManager

app = FastAPI()
gemini = GeminiClient()
manager = SessionManager()

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    session_id = str(id(ws))
    session = manager.get_or_create(session_id)
    buffer = "" # Stitches broken JSON fragments

    try:
        while True:
            # 1. Receive data (with 20s heartbeat for Render)
            try:
                raw = await asyncio.wait_for(ws.receive_text(), timeout=20.0)
                buffer += raw
            except asyncio.TimeoutError:
                await ws.send_json({"event": "ping"})
                continue

            # 2. Extract complete JSON objects
            while "{" in buffer and "}" in buffer:
                start = buffer.find("{")
                depth, end = 0, -1
                for i in range(start, len(buffer)):
                    if buffer[i] == "{": depth += 1
                    elif buffer[i] == "}":
                        depth -= 1
                        if depth == 0:
                            end = i + 1
                            break
                if end != -1:
                    obj_str = buffer[start:end]
                    buffer = buffer[end:]
                    try:
                        session.add_data(json.loads(obj_str))
                    except: continue
                else: break

            # 3. The 1000ms Trigger
            if session.is_ready_to_ask():
                audio, image = session.get_multimodal_payload()
                
                # Call Gemini 3 Pro
                response = await gemini.ask_foreman(audio, image, session.history)
                
                # Send to glasses in small 300-char bursts
                chunks = [response[i:i+300] for i in range(0, len(response), 300)]
                for i, chunk in enumerate(chunks):
                    await ws.send_json({
                        "event": "ai_result",
                        "data": {"speech_text": chunk, "is_final": i == len(chunks)-1}
                    })
    except WebSocketDisconnect:
        manager.delete_session(session_id)
