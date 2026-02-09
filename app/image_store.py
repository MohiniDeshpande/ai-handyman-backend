import time
import uuid

_STORE: dict[str, tuple[bytes, str, float]] = {}
TTL_SECONDS = 180  # keep generated images for 3 minutes

def purge() -> None:
    now = time.time()
    dead = [k for k, (_, __, ts) in _STORE.items() if now - ts > TTL_SECONDS]
    for k in dead:
        _STORE.pop(k, None)

def put_image(img_bytes: bytes, mime: str) -> str:
    purge()
    image_id = uuid.uuid4().hex[:12]
    _STORE[image_id] = (img_bytes, mime, time.time())
    return image_id

def get_image(image_id: str):
    purge()
    return _STORE.get(image_id)
