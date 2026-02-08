import uuid

class Session:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.audio_buffer = []
        self.latest_video = None
        self.is_recording = False # Tracks if the button is held

    def reset_audio(self):
        self.audio_buffer = []

class SessionManager:
    def __init__(self):
        self.sessions = {}

    def get_or_create(self):
        sid = str(uuid.uuid4())[:8]
        self.sessions[sid] = Session(sid)
        return self.sessions[sid]

    def remove(self, sid):
        if sid in self.sessions:
            del self.sessions[sid]
