"""UDP audio ingestion service for Whisper input."""

from __future__ import annotations

import logging
import queue
import socket
import struct
import threading
import time

import numpy as np
from scipy.signal import resample_poly

from pc.runtime_config import RuntimeConfig

AUDIO_HEADER = struct.Struct("!IH")
MAX_UDP_PACKET = 65535


class AudioReceiverService(threading.Thread):
    def __init__(
        self,
        audio_queue: queue.Queue[tuple[np.ndarray, float]],
        stop_event: threading.Event,
        config: RuntimeConfig,
        on_rms,
        on_packet,
        logger: logging.Logger,
        udp_host: str,
        udp_port: int,
    ) -> None:
        super().__init__(daemon=True)
        self.audio_queue = audio_queue
        self.stop_event = stop_event
        self.config = config
        self.on_rms = on_rms
        self.on_packet = on_packet
        self.logger = logger
        self.udp_host = udp_host
        self.udp_port = udp_port
        self.sock: socket.socket | None = None

    def run(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind((self.udp_host, self.udp_port))
        except OSError:
            self.logger.exception("Audio receiver failed to bind %s:%s", self.udp_host, self.udp_port)
            sock.close()
            return
        sock.settimeout(0.5)
        self.sock = sock
        last_rms_ui_push = 0.0
        rms_ui_interval = 1.0 / 30.0
        packet_count = 0
        self.logger.info("Audio receiver listening on %s:%s", self.udp_host, self.udp_port)

        try:
            while not self.stop_event.is_set():
                try:
                    packet, _addr = sock.recvfrom(MAX_UDP_PACKET)
                except socket.timeout:
                    continue
                except OSError:
                    break

                if len(packet) <= AUDIO_HEADER.size:
                    continue

                self.on_packet()
                packet_count += 1
                _seq, _frame_count = AUDIO_HEADER.unpack_from(packet)
                pcm = packet[AUDIO_HEADER.size :]
                if not pcm:
                    continue

                int16_samples = np.frombuffer(pcm, dtype=np.int16)
                if int16_samples.size == 0:
                    continue

                rms = float(np.sqrt(np.mean(np.square(int16_samples.astype(np.float32) / 32768.0))))
                now = time.monotonic()
                if (now - last_rms_ui_push) >= rms_ui_interval:
                    self.on_rms(rms)
                    last_rms_ui_push = now
                if packet_count % 50 == 0:
                    self.logger.info(
                        "Microphone activity | packets=%s rms=%.4f audio_enabled=%s queue_depth=%s",
                        packet_count,
                        rms,
                        self.config.is_audio_enabled(),
                        self.audio_queue.qsize(),
                    )

                if not self.config.is_audio_enabled():
                    continue

                downsampled = resample_poly(int16_samples.astype(np.float32), up=1, down=3)
                whisper_chunk = np.clip(downsampled / 32768.0, -1.0, 1.0).astype(np.float32)
                try:
                    self.audio_queue.put_nowait((whisper_chunk, rms))
                except queue.Full:
                    queue_depth = self.audio_queue.qsize()
                    self.logger.warning(
                        "Audio queue full (depth=%s); dropping oldest chunk to make room",
                        queue_depth,
                    )
                    dropped = False
                    try:
                        self.audio_queue.get_nowait()
                        dropped = True
                    except queue.Empty:
                        pass
                    
                    if dropped:
                        try:
                            self.audio_queue.put_nowait((whisper_chunk, rms))
                        except queue.Full:
                            self.logger.warning("Audio queue still full after drop; chunk discarded")
                    else:
                        self.logger.warning("Could not drain audio queue; chunk discarded")
        finally:
            sock.close()
            self.logger.info("Audio receiver stopped")

    def close_socket(self) -> None:
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
