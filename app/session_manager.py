import base64
import re
import time

class Session:
    def __init__(self, session_id):
        self.session_id = session_id
        self.audio_buffer = []
        self.last_frame = None
        self.history = []  # Stores the conversation turns
        self.last_activity = time.time()

    def add_data(self, data):
        """Routes incoming WebSocket JSON to the right buffer."""
        self.last_activity = time.time()
        if data.get("type") == "audio":
            self.audio_buffer.append(data.get("value"))
        elif data.get("type") == "video":
            self.last_frame = data.get("value")

    def is_ready_to_ask(self):
        """
        Triggers at the 1000ms mark. 
        Assumes 25 chunks of 40ms each = 1 second of audio.
        """
        audio_chunk_count = len(self.audio_buffer)
        
        # Log every 5 chunks so you can see it filling up in Render logs
        if audio_chunk_count % 5 == 0 and audio_chunk_count > 0:
            print(f"DEBUG: Buffer at {audio_chunk_count}/25 chunks")
    
        return audio_chunk_count >= 25

    def get_multimodal_payload(self):
        """Point 1 & 6: Combines audio chunks into one clean byte stream."""
        combined_audio = b"".join([base64.b64decode(c) for c in self.audio_buffer])
        image_bytes = base64.b64decode(self.last_frame) if self.last_frame else None
        
        # Clear buffer after grabbing payload to prevent repeat-firing
        self.audio_buffer = [] 
        return combined_audio, image_bytes

    def prepare_chunks_for_spectacles(self, text, limit=385):
        """
        Point 3, 9: The Savior for 'Error 13'.
        Splits text into chunks under 400 chars, breaking at sentences.
        """
        # Split by punctuation followed by space
        sentences = re.split(r'(?<=[.!?]) +', text.strip())
        chunks = []
        current_chunk = ""

        for s in sentences:
            if len(current_chunk) + len(s) < limit:
                current_chunk += (" " + s if current_chunk else s)
            else:
                chunks.append(current_chunk.strip())
                current_chunk = s
        
        if current_chunk:
            chunks.append(current_chunk.strip())
            
        return chunks

class SessionManager:
    def __init__(self):
        self.sessions = {}

    def get_or_create(self, session_id):
        if session_id not in self.sessions:
            self.sessions[session_id] = Session(session_id)
        return self.sessions[session_id]

    def delete_session(self, session_id):
        if session_id in self.sessions:
            del self.sessions[session_id]
