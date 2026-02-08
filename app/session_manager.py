import uuid
import time
from typing import Dict, Optional, List

class Session:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.audio_buffer: List[str] = []  # Stores base64 PCM chunks
        self.latest_video: Optional[str] = None
        self.last_activity = time.time()
        self.is_recording = False

    def reset_audio(self):
        self.audio_buffer = []
        print(f">>> [LOG] Session {self.session_id}: Audio buffer reset.")

class SessionManager:
    def __init__(self, timeout_seconds: int = 600):
        self.sessions: Dict[str, Session] = {}
        self.timeout_seconds = timeout_seconds

    def get_or_create(self, session_id: Optional[str] = None) -> Session:
        # Create a short ID for cleaner Render logs
        new_id = str(uuid.uuid4())[:8]
        self.sessions[new_id] = Session(new_id)
        print(f">>> [LOG] Session Created: {new_id}")
        return self.sessions[new_id]

    def remove(self, session_id: str):
        if session_id in self.sessions:
            del self.sessions[session_id]
            print(f">>> [LOG] Session Removed: {session_id}")
