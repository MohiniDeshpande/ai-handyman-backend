import asyncio
import time


class SessionManager:
    def __init__(self, ws, timeout, warning):
        self.ws = ws
        self.timeout = timeout
        self.warning = warning
        self.last_active = time.time()
        self.warned = False

    def touch(self):
        self.last_active = time.time()
        self.warned = False

    async def monitor(self):
        while True:
            await asyncio.sleep(1)
            elapsed = time.time() - self.last_active

            if elapsed > self.timeout - self.warning and not self.warned:
                await self.ws.send_json({
                    "type": "warning",
                    "message": "Session will close in 15 seconds due to inactivity"
                })
                self.warned = True

            if elapsed > self.timeout:
                await self.ws.close()
                break

