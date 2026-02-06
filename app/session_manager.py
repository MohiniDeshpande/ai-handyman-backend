import asyncio
import time

class SessionManager:
    def __init__(self, websocket, timeout, warning_time):
        self.websocket = websocket
        self.timeout = timeout
        self.warning_time = warning_time
        self.last_activity = time.time()
        self.warning_sent = False

    def touch(self):
        self.last_activity = time.time()
        self.warning_sent = False

    async def monitor(self):
        while True:
            await asyncio.sleep(1)
            elapsed = time.time() - self.last_activity

            if elapsed > self.timeout - self.warning_time and not self.warning_sent:
                await self.websocket.send_json({
                    "type": "warning",
                    "message": "Session will close in 15 seconds due to inactivity"
                })
                self.warning_sent = True

            if elapsed > self.timeout:
                await self.websocket.send_json({
                    "type": "session_closed",
                    "reason": "inactivity"
                })
                await self.websocket.close()
                break
