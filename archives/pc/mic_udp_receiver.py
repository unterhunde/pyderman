"""UDP audio receiver that plays back a Pi microphone stream in real time.

The Pi sender prefixes each UDP packet with a compact header:

    sequence_number (uint32), num_frames (uint16)

This class receives those packets and plays them back through the system
audio output using PyAudio.

Example usage from client.py:

    from pc.mic_udp_receiver import UDPAudioReceiver

    audio = UDPAudioReceiver(port=5001)
    audio.start()
"""

from __future__ import annotations

import socket
import struct
import threading
import time
from collections import deque
from pathlib import Path
import sys

import pyaudio

sys.path.append(str(Path(__file__).resolve().parents[1]))
from pibot_config import load_settings

SETTINGS = load_settings()

# Packet layout shared with the Pi sender in pi/mic_udp_streamer.py.
AUDIO_HEADER = struct.Struct("!IH")
MAX_PACKET_SIZE = 65535

SAMPLE_RATE = 48000
CHANNELS = 1
FORMAT = pyaudio.paInt16
CHUNK_FRAMES = 1024

# Chunks to buffer before playback begins — reduces underruns on slow networks.
BUFFER_CHUNKS = 4


class UDPAudioReceiver:
    """Receives a UDP PCM audio stream from the Pi and plays it back.

    Thread model:
    - A daemon receive thread reads UDP packets and fills an in-memory deque.
    - A PyAudio stream callback drains that deque to feed the audio hardware.

    Call ``start()`` to begin and ``stop()`` / ``close()`` to tear down.
    """

    def __init__(
        self,
        host: str = SETTINGS.udp_bind_host,
        port: int = SETTINGS.udp_audio_port,
        sample_rate: int = SAMPLE_RATE,
        channels: int = CHANNELS,
        chunk_frames: int = CHUNK_FRAMES,
        buffer_chunks: int = BUFFER_CHUNKS,
    ) -> None:
        self.host = host
        self.port = port
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_frames = chunk_frames
        self.buffer_chunks = buffer_chunks

        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.bind((self.host, self.port))
        self._socket.settimeout(0.5)

        # Hold enough chunks to smooth over brief network gaps.
        self._buffer: deque[bytes] = deque(maxlen=buffer_chunks * 4)
        # One silent chunk reused whenever the buffer runs dry.
        self._silence = b"\x00" * chunk_frames * 2  # paInt16 → 2 bytes per frame

        self._pa = pyaudio.PyAudio()
        self._stream: pyaudio.Stream | None = None
        self._recv_thread: threading.Thread | None = None
        self._running = False
        self._primed = False

    def start(self) -> None:
        """Open the audio output stream and begin receiving packets."""
        if self._running:
            return

        self._running = True

        self._stream = self._pa.open(
            format=FORMAT,
            channels=self.channels,
            rate=self.sample_rate,
            output=True,
            frames_per_buffer=self.chunk_frames,
            stream_callback=self._audio_callback,
        )
        self._stream.start_stream()

        self._recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self._recv_thread.start()

    def stop(self) -> None:
        """Stop playback and the receive thread."""
        self._running = False
        self._primed = False
        self._buffer.clear()

        if self._stream is not None:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None

        if self._recv_thread is not None:
            self._recv_thread.join(timeout=2.0)
            self._recv_thread = None

    def close(self) -> None:
        """Stop the receiver and release all resources."""
        self.stop()
        self._socket.close()
        self._pa.terminate()

    def _recv_loop(self) -> None:
        """Background thread: pull UDP packets and push PCM data into the buffer."""
        while self._running:
            try:
                packet, _addr = self._socket.recvfrom(MAX_PACKET_SIZE)
            except socket.timeout:
                continue
            except OSError:
                break

            if len(packet) < AUDIO_HEADER.size:
                continue

            _seq, _num_frames = AUDIO_HEADER.unpack_from(packet)
            pcm_data = packet[AUDIO_HEADER.size:]
            if pcm_data:
                self._buffer.append(pcm_data)

    def _audio_callback(
        self,
        in_data: bytes | None,
        frame_count: int,
        time_info: dict,
        status_flags: int,
    ) -> tuple[bytes, int]:
        """PyAudio callback: pull the next chunk from the buffer or emit silence."""
        if not self._primed:
            if len(self._buffer) >= self.buffer_chunks:
                self._primed = True
            else:
                return self._silence, pyaudio.paContinue

        try:
            data = self._buffer.popleft()
        except IndexError:
            # Buffer underrun: re-enter pre-roll mode to avoid stutter bursts.
            self._primed = False
            data = self._silence

        # Ensure exactly the byte count PyAudio expects.
        expected = frame_count * self.channels * 2  # paInt16 → 2 bytes per frame
        if len(data) < expected:
            data = data + b"\x00" * (expected - len(data))
        elif len(data) > expected:
            data = data[:expected]

        return data, pyaudio.paContinue


if __name__ == "__main__":
    receiver = UDPAudioReceiver(port=SETTINGS.udp_audio_port)
    print(f"Listening for audio on UDP port {SETTINGS.udp_audio_port} ... Press Ctrl+C to stop.")
    receiver.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        receiver.close()
        print("Stopped.")
