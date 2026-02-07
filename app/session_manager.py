# session_manager.py

from fastapi import WebSocket

class SessionManager:
    def __init__(self, ws: WebSocket = None, timeout: int = 3600, warning: bool = True):
        self.ws = ws
        self.timeout = timeout
        self.warning = warning
        self.active = True

    async def close(self):
        self.active = False
        if self.ws:
            await self.ws.close()
