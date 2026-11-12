"""Listening and speaking, both offline and free.

- Listening uses Vosk (https://alphacephei.com/vosk/models), which runs on the
  computer with no internet and no account. Download a small model (~50 MB)
  for the person's language and point "speech_model_path" at the folder.
- Speaking uses the voice built into Windows, macOS or Linux (pyttsx3).

Needs: pip install vosk sounddevice pyttsx3
"""
from __future__ import annotations

import json
import queue
import threading
import time


class Listener:
    SAMPLE_RATE = 16000

    def __init__(self, model_path: str):
        from vosk import Model, SetLogLevel

        SetLogLevel(-1)
        if not model_path:
            raise RuntimeError("No speech model set. See the README: 'Download a voice model'.")
        self.model = Model(model_path)

    def listen_once(self, max_seconds: float = 8.0, silence_seconds: float = 1.5) -> str:
        """Record until they stop talking (or max_seconds) and return the words heard."""
        import sounddevice as sd
        from vosk import KaldiRecognizer

        rec = KaldiRecognizer(self.model, self.SAMPLE_RATE)
        audio: queue.Queue[bytes] = queue.Queue()

        def callback(indata, frames, t, status):
            audio.put(bytes(indata))

        start = time.monotonic()
        last_words = start
        text = ""
        with sd.RawInputStream(samplerate=self.SAMPLE_RATE, blocksize=4000, dtype="int16",
                               channels=1, callback=callback):
            while time.monotonic() - start < max_seconds:
                try:
                    chunk = audio.get(timeout=0.5)
                except queue.Empty:
                    continue
                if rec.AcceptWaveform(chunk):
                    text = (text + " " + json.loads(rec.Result()).get("text", "")).strip()
                    if text:
                        break
                elif json.loads(rec.PartialResult()).get("partial"):
                    last_words = time.monotonic()
                elif text == "" and time.monotonic() - last_words > max(silence_seconds, 4.0):
                    break  # nobody spoke
        if not text:
            text = json.loads(rec.FinalResult()).get("text", "")
        return text.strip()


class Speaker:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._lock = threading.Lock()
        self._engine = None
        if enabled:
            try:
                import pyttsx3

                self._engine = pyttsx3.init()
                self._engine.setProperty("rate", 150)  # a little slower than normal
            except Exception:
                self._engine = None

    def say(self, text: str) -> None:
        if not (self.enabled and self._engine and text):
            return
        with self._lock:
            self._engine.say(text)
            self._engine.runAndWait()
