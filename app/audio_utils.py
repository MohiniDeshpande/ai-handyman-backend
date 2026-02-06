import base64

def pcm16_to_base64(pcm_bytes: bytes) -> str:
    return base64.b64encode(pcm_bytes).decode("utf-8")
