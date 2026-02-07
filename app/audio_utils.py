import base64
import numpy as np
from typing import Union

def pcm16_to_base64(pcm_bytes: bytes) -> str:
    """Convert PCM16 bytes to base64 string."""
    return base64.b64encode(pcm_bytes).decode("utf-8")

def float32_to_pcm16(audio_frame: np.ndarray) -> bytes:
    """Convert Float32 numpy array to PCM16 bytes."""
    clipped = np.clip(audio_frame, -1.0, 1.0)
    pcm16 = (clipped * 32767).astype(np.int16)
    return pcm16.tobytes()

def prepare_audio_frame(audio_frame: Union[bytes, np.ndarray]) -> str:
    """Prepare audio for sending to Gemini."""
    if isinstance(audio_frame, np.ndarray):
        pcm_bytes = float32_to_pcm16(audio_frame)
    else:
        pcm_bytes = audio_frame
    return pcm16_to_base64(pcm_bytes)

