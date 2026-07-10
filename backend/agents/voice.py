import os
import sys
from faster_whisper import WhisperModel

class VoiceAgent:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        print("Initializing VoiceAgent with faster-whisper base model on CPU...", flush=True)
        # compute_type="int8" is highly optimized for CPU inference
        self.model = WhisperModel("base", device="cpu", compute_type="int8")
        print("VoiceAgent initialized successfully.", flush=True)

    def transcribe(self, audio_path: str) -> str:
        try:
            print(f"Transcribing audio file: {audio_path}", flush=True)
            segments, info = self.model.transcribe(audio_path, beam_size=5, language="en")
            
            text_list = []
            for segment in segments:
                text_list.append(segment.text)
                
            full_text = " ".join(text_list).strip()
            print(f"Transcription result: '{full_text}'", flush=True)
            return full_text
        except Exception as e:
            print(f"Error during transcription: {e}", file=sys.stderr, flush=True)
            raise e
