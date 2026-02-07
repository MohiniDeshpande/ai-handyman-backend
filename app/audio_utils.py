# audio_utils.py
import numpy as np
import base64

def float32_to_pcm16(audio_frame: np.ndarray) -> bytes:
    audio_frame = np.clip(audio_frame, -1, 1)
    pcm16 = (audio_frame * np.where(audio_frame < 0, 32768, 32767)).astype(np.int16)
    return pcm16.tobytes()

def pcm16_to_base64(pcm_bytes: bytes) -> str:
    return base64.b64encode(pcm_bytes).decode("utf-8")


