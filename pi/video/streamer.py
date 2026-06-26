"""UDP video streaming service."""

from __future__ import annotations

import logging
import signal
import socket
import time

import cv2

from pi.video.config import FPS, JPEG_QUALITY
from pi.video.frame_source import open_camera, synthetic_frame
from pi.video.protocol import CHUNK_HEADER, MAX_UDP_PAYLOAD, PACKET_TYPE_HEARTBEAT, HEARTBEAT_PACKET

logger = logging.getLogger("pibot.video_streamer")


def configure_logging() -> None:
    if logger.handlers:
        return
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )


class UDPVideoStreamer:
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.shutdown_requested = False
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum: int, frame) -> None:
        """Handle SIGTERM and SIGINT gracefully."""
        signal_name = signal.Signals(signum).name
        logger.info("Received signal %s, initiating graceful shutdown", signal_name)
        self.shutdown_requested = True

    def run(self) -> None:
        configure_logging()
        logger.info("Video streamer start: destination=%s:%s", self.host, self.port)
        video_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        destination = (self.host, self.port)
        video_sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 2 * 1024 * 1024)

        picam2, source_type = open_camera()

        encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]
        frame_id = 0
        frame_interval = 1.0 / FPS if FPS > 0 else 0
        next_frame_time = time.perf_counter()
        started = time.perf_counter()
        sent_packets = 0
        sent_bytes = 0
        encode_failures = 0
        last_heartbeat_time = time.perf_counter()
        heartbeat_interval = 0.5  # Send heartbeat every 500ms

        try:
            while True:
                # Check if shutdown was requested
                if self.shutdown_requested:
                    logger.info("Shutdown requested, exiting main loop")
                    break
                
                now = time.perf_counter()
                
                # Send heartbeat if interval exceeded
                if (now - last_heartbeat_time) >= heartbeat_interval:
                    heartbeat_ms = int((now - started) * 1000) & 0xFFFFFFFFFFFFFFFF
                    heartbeat = HEARTBEAT_PACKET.pack(PACKET_TYPE_HEARTBEAT, heartbeat_ms)
                    try:
                        video_sock.sendto(heartbeat, destination)
                        sent_packets += 1
                        sent_bytes += len(heartbeat)
                    except OSError:
                        logger.warning("Failed to send heartbeat packet")
                    last_heartbeat_time = now
                
                if picam2 is not None:
                    frame = picam2.capture_array("main")
                else:
                    frame = synthetic_frame(frame_id)

                if frame is None or frame.size == 0:
                    logger.warning("Empty frame captured at frame_id=%s", frame_id)
                    continue

                ok, encoded = cv2.imencode(".jpg", frame, encode_params)
                if not ok:
                    encode_failures += 1
                    if encode_failures % 20 == 0:
                        logger.warning("JPEG encode failures=%s", encode_failures)
                    continue

                payload = encoded.tobytes()
                total_chunks = (len(payload) + MAX_UDP_PAYLOAD - 1) // MAX_UDP_PAYLOAD
                if total_chunks > 65535:
                    logger.warning("Skipping oversized frame: bytes=%s chunks=%s", len(payload), total_chunks)
                    continue

                for chunk_index in range(total_chunks):
                    start = chunk_index * MAX_UDP_PAYLOAD
                    end = start + MAX_UDP_PAYLOAD
                    chunk = payload[start:end]
                    header = CHUNK_HEADER.pack(frame_id, total_chunks, chunk_index)
                    packet = header + chunk
                    video_sock.sendto(packet, destination)
                    sent_packets += 1
                    sent_bytes += len(packet)

                frame_id = (frame_id + 1) & 0xFFFFFFFF
                if frame_id % 30 == 0:
                    elapsed = max(0.001, time.perf_counter() - started)
                    fps = frame_id / elapsed
                    logger.info(
                        "Source=%s | captured=%s frames | fps=%.2f | encoded=%sx%s | packets=%s | bytes=%s",
                        source_type,
                        frame_id,
                        fps,
                        frame.shape[1],
                        frame.shape[0],
                        sent_packets,
                        sent_bytes,
                    )

                if frame_interval > 0:
                    next_frame_time += frame_interval
                    sleep_for = next_frame_time - time.perf_counter()
                    if sleep_for > 0:
                        time.sleep(sleep_for)
                    else:
                        next_frame_time = time.perf_counter()
        except KeyboardInterrupt:
            logger.info("Video streamer interrupted by user")
        except Exception as exc:
            logger.exception("Video streamer error: %s", exc)
        finally:
            if picam2 is not None:
                picam2.stop()
            video_sock.close()
            logger.info(
                "Video streamer stopped: frames=%s packets=%s bytes=%s encode_failures=%s",
                frame_id,
                sent_packets,
                sent_bytes,
                encode_failures,
            )

