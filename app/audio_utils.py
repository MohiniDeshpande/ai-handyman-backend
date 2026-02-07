# audio_utils.py
import numpy as np
import base64

def float32_to_pcm16(audio_frame: np.ndarray) -> bytes:
    clipped = np.clip(audio_frame, -1.0, 1.0)
    pcm16 = (clipped * 32767).astype(np.int16)
    return pcm16.tobytes()

def pcm16_to_base64(pcm_bytes: bytes) -> str:
    return base64.b64encode(pcm_bytes).decode("utf-8")

def prepare_audio_frame(audio_frame: np.ndarray) -> str:
    pcm_bytes = float32_to_pcm16(audio_frame)
    return pcm16_to_base64(pcm_bytes)

