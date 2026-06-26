"""Thread-safe runtime toggles for audio/listening controls."""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass
class RuntimeConfig:
    volume_threshold: float = 0.045
    silence_timeout: float = 1.2
    audio_stream_enabled: bool = True
    listening_enabled: bool = True

    def __post_init__(self) -> None:
        self._lock = threading.Lock()

    def set_threshold(self, value: float) -> None:
        with self._lock:
            self.volume_threshold = value

    def get_threshold(self) -> float:
        with self._lock:
            return self.volume_threshold

    def set_silence_timeout(self, value: float) -> None:
        with self._lock:
            self.silence_timeout = value

    def get_silence_timeout(self) -> float:
        with self._lock:
            return self.silence_timeout

    def set_audio_enabled(self, enabled: bool) -> None:
        with self._lock:
            self.audio_stream_enabled = enabled

    def is_audio_enabled(self) -> bool:
        with self._lock:
            return self.audio_stream_enabled

    def set_listening_enabled(self, enabled: bool) -> None:
        with self._lock:
            self.listening_enabled = enabled

    def is_listening_enabled(self) -> bool:
        with self._lock:
            return self.listening_enabled

