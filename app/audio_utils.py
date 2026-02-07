import json
import base64
from io import BytesIO
from PIL import Image

# ---------- Helper Functions ----------

def pcm16_to_base64(pcm_bytes):
    
    return base64.b64encode(pcm_bytes).decode("utf-8")


def needs_image(user_text: str) -> bool:

    keywords = ["image", "picture", "draw", "show"]
    return any(k in user_text.lower() for k in keywords)


def text_response(conversation):

    last_user_msg = conversation[-1]["parts"][0].get("text", "")
    return {
        "candidates": [
            {"content": f"Echo: {last_user_msg}"}
        ]
    }


def image_response(conversation):
   
    # Dummy image example: red square
    img = Image.new("RGB", (256, 256), color=(255, 0, 0))
    
    # Convert to bytes
    buf = BytesIO()
    img.save(buf, format="PNG")
    image_bytes = buf.getvalue()
    
    # Encode as base64
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    
    # Return JSON-ready dict
    return {
        "candidates": [
            {
                "content": {
                    "inline_data": {
                        "mime_type": "image/png",
                        "data": image_b64
                    }
                }
            }
        ]
    }
