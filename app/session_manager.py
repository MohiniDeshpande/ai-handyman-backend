import uuid
import time

class Session:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.audio_buffer = []
        self.latest_video = None
        self.last_activity = time.time()
        self.is_recording = False
        self.processing = False  # prevent overlapping Gemini calls


class SessionManager:
    def __init__(self):
        self.sessions = {}

    def get_or_create(self, session_id: str = None) -> Session:
        if not session_id or session_id not in self.sessions:
            session_id = str(uuid.uuid4())[:8]
            self.sessions[session_id] = Session(session_id)
            print(f">>> [SESSION CREATED] {session_id}")

        session = self.sessions[session_id]
        session.last_activity = time.time()
        return session

    def remove(self, session_id: str):
        if session_id in self.sessions:
            del self.sessions[session_id]
            print(f">>> [SESSION REMOVED] {session_id}")
