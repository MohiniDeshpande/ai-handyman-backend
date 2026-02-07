import base64

def decode_video_frame(b64_image: str) -> bytes:
    """
    Input: base64 image (jpg/png) WITHOUT data URL prefix
    Output: raw image bytes
    """
    return base64.b64decode(b64_image)
