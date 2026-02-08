import uuid
import time
from typing import Dict, List, Optional

class Session:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.audio_buffer: List[str] = []
        self.latest_video: Optional[str] = None
        self.is_recording = False
        self.last_activity = time.time()

    def reset_audio(self):
        self.audio_buffer = []

class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, Session] = {}

    def get_or_create(self) -> Session:
        # Create a clean session with an 8-char ID for easier Render logging
        session_id = str(uuid.uuid4())[:8]
        self.sessions[session_id] = Session(session_id)
        print(f">>> [LOG] Session Created: {session_id}")
        return self.sessions[session_id]

    def remove(self, session_id: str):
        if session_id in self.sessions:
            del self.sessions[session_id]
            print(f">>> [LOG] Session Removed: {session_id}")
