import json
import asyncio
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from .session_manager import SessionManager
from .gemini_client import GeminiClient

# Setup logging to see what's happening in real-time
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
sessions = SessionManager()
gemini_client = GeminiClient()

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    session_id = sessions.create()
    
    # This is the "Visual Memory" for this specific handyman session
    # It ensures that when a user says "How do I fix this?", 
    # the AI actually has the "this" (the image) in its context.
    latest_frame_b64 = None

    logger.info(f"New Handyman Session Started: {session_id}")

    try:
        # Send initial confirmation to frontend
        await ws.send_text(json.dumps({
            "type": "system",
            "message": "Connected to Handyman AI. Send video frames to start.",
            "session_id": session_id
        }))

        while True:
            # Receive JSON message from the frontend
            msg = await ws.receive_text()
            data = json.loads(msg)

            # --- ROUTE 1: UPDATE VISUAL CONTEXT ---
            # The frontend should stream frames frequently (e.g., 1 per second)
            if "image_b64" in data:
                latest_frame_b64 = data["image_b64"]
                # We don't reply to every frame to save bandwidth/latency
                continue

            # --- ROUTE 2: MULTIMODAL QUERY (REASONING) ---
            # Triggered when user speaks (audio_b64) or types (text)
            if "audio_b64" in data or "text" in data:
                user_text = data.get("text")
                user_audio = data.get("audio_b64")

                try:
                    # Request analysis from Gemini 3 Pro Preview
                    # We pass the LATEST frame as the visual context
                    ai_response = await gemini_client.analyze_multimodal(
                        text=user_text,
                        audio_b64=user_audio,
                        image_b64=latest_frame_b64
                    )

                    # Extract AI's textual guidance
                    ai_text = ai_response['candidates'][0]['content']['parts'][0].get('text', '')
                    
                    # Send text response back to user
                    await ws.send_text(json.dumps({
                        "type": "ai_guidance",
                        "text": ai_text
                    }))

                    # --- ROUTE 3: AUTOMATIC DIAGRAM GENERATION ---
                    # If the AI suggests a repair step that needs a visual aid,
                    # we trigger Gemini 3 Pro Image Preview.
                    if any(word in ai_text.lower() for word in ["diagram", "visualize", "show you how"]):
                        logger.info("Triggering Image Generation for repair diagram...")
                        image_data = await gemini_client.generate_handyman_visual(ai_text)
                        
                        await ws.send_text(json.dumps({
                            "type": "repair_diagram",
                            "image_url": image_data.get("url") # Assuming 2026 API returns a URL
                        }))

                except Exception as e:
                    logger.error(f"Gemini API Error: {str(e)}")
                    await ws.send_text(json.dumps({"type": "error", "message": "AI failed to process request."}))

    except WebSocketDisconnect:
        logger.info(f"Session {session_id} ended by user.")
    except Exception as e:
        logger.error(f"Unexpected error in session {session_id}: {e}")
    finally:
        sessions.remove(session_id)
