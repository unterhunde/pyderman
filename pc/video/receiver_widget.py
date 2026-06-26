"""Tk widget for UDP video receive, decode, and preview/inference rendering."""

from __future__ import annotations

import logging
import queue
import socket
import threading
import time
import tkinter as tk
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageTk

from pc.video.frame_buffer import FrameBuffer
from pc.video.inference_engine import InferenceEngine
from pc.video.protocol import CHUNK_HEADER, MAX_PACKET_SIZE, PACKET_TYPE_CHUNK, PACKET_TYPE_HEARTBEAT, HEARTBEAT_PACKET

sys.path.append(str(Path(__file__).resolve().parents[2]))
from pibot_config import load_settings

logging.getLogger("ultralytics").setLevel(logging.WARNING)
SETTINGS = load_settings()
logger = logging.getLogger("pibot.video_receiver")


class UDPVideoReceiver(tk.Label):
    def __init__(
        self,
        master: tk.Misc,
        host: str = SETTINGS.udp_bind_host,
        port: int = SETTINGS.udp_video_port,
        poll_interval_ms: int = 15,
        max_buffered_frames: int = 4,
        model_path: str = SETTINGS.yolo_model_path,
        inference_enabled: bool = True,
        status_callback=None,
        stats_callback=None,
        packet_callback=None,
        **kwargs,
    ) -> None:
        label_kwargs = {
            "text": "Waiting for UDP video...",
            "compound": tk.CENTER,
            "anchor": tk.CENTER,
            "bg": "black",
            "fg": "white",
        }
        label_kwargs.update(kwargs)
        super().__init__(master, **label_kwargs)

        self.host = host
        self.port = port
        self.poll_interval_ms = poll_interval_ms
        self.max_buffered_frames = max_buffered_frames
        self.model_path = model_path
        self.status_callback = status_callback
        self.stats_callback = stats_callback
        self.packet_callback = packet_callback

        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
        self._socket.bind((self.host, self.port))
        self._socket.setblocking(False)

        self._frames: dict[int, FrameBuffer] = {}
        self._latest_completed_frame = -1
        self._photo_image: ImageTk.PhotoImage | None = None
        self._poll_job: str | None = None
        self._running = False
        self._render_queue: queue.Queue[tuple[int, bytes]] = queue.Queue(maxsize=2)
        self._ui_queue: queue.Queue[tuple[str, object]] = queue.Queue(maxsize=8)
        self._worker_stop = threading.Event()
        self._worker_thread: threading.Thread | None = None
        self._inference_enabled = inference_enabled
        self._inference_lock = threading.Lock()
        self._engine = InferenceEngine(model_path=self.model_path)
        self._last_frame_time = 0.0
        self._last_fps = 0.0
        self._saw_first_packet = False
        self._received_packets = 0
        self._received_bytes = 0
        self._decode_failures = 0
        self._rendered_frames = 0
        self._last_diag_time = time.perf_counter()
        self._model_loaded = False
        self._last_heartbeat_time = 0.0  # Track heartbeat separately from video packets

    def start(self) -> None:
        if self._running:
            return
        self._frames.clear()
        self._latest_completed_frame = -1
        self._saw_first_packet = False
        self._worker_stop.clear()
        self._start_worker()
        self._running = True
        self._schedule_poll()
        self._emit_status(f"Video receiver listening on {self.host}:{self.port}")

    def stop(self) -> None:
        self._running = False
        if self._poll_job is not None:
            self.after_cancel(self._poll_job)
            self._poll_job = None
        self._worker_stop.set()
        if self._worker_thread is not None:
            self._worker_thread.join(timeout=1.0)
            self._worker_thread = None
        self._clear_render_queue()
        self._emit_status("Video receiver stopped")

    def destroy(self) -> None:
        self.stop()
        self._socket.close()
        super().destroy()

    def set_inference_enabled(self, enabled: bool) -> None:
        with self._inference_lock:
            self._inference_enabled = enabled
        state = "enabled" if enabled else "disabled"
        self._emit_status(f"Video inference {state}")

    def _schedule_poll(self) -> None:
        if self._running:
            self._poll_job = self.after(self.poll_interval_ms, self._poll_socket)

    def _poll_socket(self) -> None:
        while True:
            try:
                packet, _addr = self._socket.recvfrom(MAX_PACKET_SIZE)
            except BlockingIOError:
                break
            except OSError:
                break
            self._handle_packet(packet)
        self._drain_ui_queue()
        self._schedule_poll()

    def _handle_packet(self, packet: bytes) -> None:
        if len(packet) < 1:
            return
        
        self._received_packets += 1
        self._received_bytes += len(packet)
        
        # Check packet type
        packet_type = packet[0]
        
        if packet_type == PACKET_TYPE_HEARTBEAT:
            # Handle heartbeat packet
            if len(packet) >= HEARTBEAT_PACKET.size:
                self._last_heartbeat_time = time.perf_counter()
                if self.packet_callback is not None:
                    self.after(0, self.packet_callback)
            return
        
        # Handle video chunk packet
        if len(packet) < CHUNK_HEADER.size:
            return
        
        if self.packet_callback is not None:
            self.after(0, self.packet_callback)
        
        if not self._saw_first_packet:
            self._saw_first_packet = True
            self._emit_status("Video UDP packets detected")
        frame_id, total_chunks, chunk_index = CHUNK_HEADER.unpack_from(packet)
        payload = packet[CHUNK_HEADER.size :]
        if total_chunks <= 0 or chunk_index >= total_chunks:
            return
        if frame_id < self._latest_completed_frame:
            return

        frame_buffer = self._frames.get(frame_id)
        if frame_buffer is None:
            frame_buffer = FrameBuffer(total_chunks=total_chunks)
            self._frames[frame_id] = frame_buffer
            self._prune_incomplete_frames()
        elif frame_buffer.total_chunks != total_chunks:
            frame_buffer = FrameBuffer(total_chunks=total_chunks)
            self._frames[frame_id] = frame_buffer

        frame_buffer.add_chunk(chunk_index, payload)
        if frame_buffer.is_complete():
            try:
                jpeg_bytes = frame_buffer.assemble()
            except ValueError as exc:
                self._frames.pop(frame_id, None)
                logger.warning("Frame reassembly failed for frame %s: %s", frame_id, exc)
                return
            self._enqueue_frame(frame_id, jpeg_bytes)

    def _prune_incomplete_frames(self) -> None:
        if len(self._frames) <= self.max_buffered_frames:
            return
        frames_to_drop = sorted(self._frames)[:-self.max_buffered_frames]
        dropped_count = len(frames_to_drop)
        self._frames = {k: v for k, v in self._frames.items() if k not in frames_to_drop}
        if dropped_count > 0:
            logger.warning(
                "Dropped %s incomplete video frame(s) due to buffer limit. Buffer size=%s",
                dropped_count,
                self.max_buffered_frames,
            )

    def _start_worker(self) -> None:
        if self._worker_thread is not None and self._worker_thread.is_alive():
            return
        self._worker_thread = threading.Thread(target=self._render_worker, daemon=True)
        self._worker_thread.start()

    def _is_inference_enabled(self) -> bool:
        with self._inference_lock:
            return self._inference_enabled

    def _queue_status(self, message: str) -> None:
        try:
            self._ui_queue.put_nowait(("status", message))
        except queue.Full:
            pass

    def _emit_status(self, message: str) -> None:
        if self.status_callback is not None:
            self.status_callback(message)

    def _emit_stats(self, frame_id: int, detection_count: int, inference_ms: float) -> None:
        now = time.perf_counter()
        if self._last_frame_time > 0:
            dt = now - self._last_frame_time
            if dt > 0:
                fps = 1.0 / dt
                self._last_fps = (self._last_fps * 0.8) + (fps * 0.2) if self._last_fps else fps
        self._last_frame_time = now
        if self.stats_callback is not None:
            self.stats_callback(
                {
                    "frame_id": frame_id,
                    "fps": self._last_fps,
                    "detection_count": detection_count,
                    "inference_ms": inference_ms,
                }
            )

    def _clear_render_queue(self) -> None:
        while True:
            try:
                self._render_queue.get_nowait()
            except queue.Empty:
                break

    def _enqueue_frame(self, frame_id: int, jpeg_bytes: bytes) -> None:
        try:
            self._render_queue.put_nowait((frame_id, jpeg_bytes))
        except queue.Full:
            try:
                self._render_queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._render_queue.put_nowait((frame_id, jpeg_bytes))
            except queue.Full:
                pass

    def _render_worker(self) -> None:
        while not self._worker_stop.is_set():
            try:
                frame_id, jpeg_bytes = self._render_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if self._is_inference_enabled() and not self._model_loaded:
                self._queue_status(f"Loading model: {self.model_path}")
                try:
                    self._engine.load_model()
                    self._model_loaded = True
                    self._queue_status(f"Model ready: {self.model_path}")
                except Exception as exc:
                    self._queue_status(f"Inference error: {exc}")
                    continue

            try:
                frame_rgb, detection_count, inference_ms = self._engine.process(
                    jpeg_bytes=jpeg_bytes,
                    inference_enabled=self._is_inference_enabled(),
                )
            except Exception as exc:
                self._queue_status(f"Inference error: {exc}")
                continue

            if frame_rgb is None:
                self._decode_failures += 1
                if self._decode_failures % 10 == 0:
                    self._emit_status(f"Decode failures={self._decode_failures}")
                continue

            try:
                self._ui_queue.put_nowait(("frame", (frame_id, frame_rgb, detection_count, inference_ms)))
            except queue.Full:
                try:
                    self._ui_queue.get_nowait()
                except queue.Empty:
                    pass
                try:
                    self._ui_queue.put_nowait(("frame", (frame_id, frame_rgb, detection_count, inference_ms)))
                except queue.Full:
                    pass
            self._emit_diag_if_due()

    def _display_frame(self, frame_id: int, frame_rgb: np.ndarray) -> None:
        image = Image.fromarray(frame_rgb)
        self._photo_image = ImageTk.PhotoImage(image=image)
        self.configure(image=self._photo_image, text="")
        self._latest_completed_frame = frame_id
        self._rendered_frames += 1
        for buffered_frame_id in list(self._frames):
            if buffered_frame_id <= frame_id:
                del self._frames[buffered_frame_id]

    def _drain_ui_queue(self) -> None:
        while True:
            try:
                event_type, payload = self._ui_queue.get_nowait()
            except queue.Empty:
                break
            if event_type == "status":
                self._emit_status(str(payload))
            elif event_type == "frame":
                frame_id, frame_rgb, detection_count, inference_ms = payload
                self._display_frame(int(frame_id), frame_rgb)
                self._emit_stats(int(frame_id), int(detection_count), float(inference_ms))

    def _emit_diag_if_due(self) -> None:
        now = time.perf_counter()
        if (now - self._last_diag_time) < 2.0:
            return
        self._last_diag_time = now
        qsize = self._render_queue.qsize()
        logger.info(
            "Video RX diag | packets=%s bytes=%s rendered=%s decode_failures=%s queue=%s",
            self._received_packets,
            self._received_bytes,
            self._rendered_frames,
            self._decode_failures,
            qsize,
        )


UDPVideoReciever = UDPVideoReceiver

