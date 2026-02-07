import base64

def decode_audio_chunk(b64_audio: str) -> bytes:
    """
    Input: base64 PCM16 audio from frontend
    Output: raw PCM16 bytes
    """
    return base64.b64decode(b64_audio)

