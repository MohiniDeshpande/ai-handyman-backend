import uuid
import time
from fastapi import WebSocket

class SessionManager:
    """
    Manages WebSocket sessions with timeout support.
    """

    def __init__(self, timeout_seconds: int = 3600, warning_seconds: int = 60, ws: WebSocket = None):
        self.sessions = {}
        self.timeout_seconds = timeout_seconds
        self.warning_seconds = warning_seconds
        self.ws = ws
        self.active = True

    def create(self):
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = {
            "created_at": time.time(),
            "last_activity": time.time()
        }
        return session_id

    def get(self, session_id: str):
        session = self.sessions.get(session_id)
        if not session:
            return None
        # Check timeout
        if time.time() - session["last_activity"] > self.timeout_seconds:
            self.remove(session_id)
            return None
        session["last_activity"] = time.time()
        return session

    def remove(self, session_id: str):
        if session_id in self.sessions:
            del self.sessions[session_id]

    def cleanup(self):
        """Remove expired sessions"""
        now = time.time()
        expired = [sid for sid, s in self.sessions.items() if now - s["last_activity"] > self.timeout_seconds]
        for sid in expired:
            self.remove(sid)

    async def close(self):
        self.active = False
        if self.ws:
            await self.ws.close()
