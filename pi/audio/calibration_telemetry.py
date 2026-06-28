"""Pi-side calibration diagnostics/control server and stage telemetry aggregation."""

from __future__ import annotations

import queue
import socket
import threading
import time
from dataclasses import dataclass
from typing import Any

from calibration_protocol import (
    MESSAGE_REQUEST,
    ParsedMessage,
    ProtocolError,
    decode_message,
    encode_message,
    make_ack,
    make_error,
    make_telemetry,
)


@dataclass
class _StageAccumulator:
    session_id: str
    stage_id: str
    stage_type: str
    start_timestamp_ms: int
    end_timestamp_ms: int | None = None
    sequence_start: int | None = None
    sequence_end: int | None = None
    last_sequence: int | None = None
    chunks_captured: int = 0
    chunks_missing: int = 0
    chunks_dropped: int = 0
    raw_rms_sum: float = 0.0
    processed_rms_sum: float = 0.0
    peak_max: float = 0.0
    clipping_sum: float = 0.0
    gate_active_count: int = 0
    agc_gain_sum: float = 0.0
    active_channel_last: int = 0

    def add_chunk(
        self,
        *,
        sequence_number: int,
        raw_rms: float,
        processed_rms: float,
        peak: float,
        clipping_ratio: float,
        gate_active: bool,
        agc_gain: float,
        active_channel: int,
    ) -> None:
        if self.sequence_start is None:
            self.sequence_start = sequence_number
        if self.last_sequence is not None:
            delta = sequence_number - self.last_sequence
            if delta <= 0:
                delta += 2**32
            if delta > 1:
                self.chunks_missing += delta - 1
        self.last_sequence = sequence_number
        self.sequence_end = sequence_number
        self.chunks_captured += 1
        self.raw_rms_sum += raw_rms
        self.processed_rms_sum += processed_rms
        self.peak_max = max(self.peak_max, peak)
        self.clipping_sum += clipping_ratio
        self.gate_active_count += 1 if gate_active else 0
        self.agc_gain_sum += agc_gain
        self.active_channel_last = active_channel

    def add_drop(self, dropped_chunks: int) -> None:
        self.chunks_dropped += max(dropped_chunks, 0)

    def summary(self, end_timestamp_ms: int) -> dict[str, Any]:
        self.end_timestamp_ms = end_timestamp_ms
        telemetry_complete = self.chunks_captured > 0 and self.sequence_start is not None and self.sequence_end is not None
        mean_divisor = max(self.chunks_captured, 1)
        return {
            "session_id": self.session_id,
            "stage_id": self.stage_id,
            "stage_type": self.stage_type,
            "start_timestamp_ms": self.start_timestamp_ms,
            "end_timestamp_ms": self.end_timestamp_ms,
            "audio_sequence_start": self.sequence_start,
            "audio_sequence_end": self.sequence_end,
            "chunks_captured": self.chunks_captured,
            "chunks_missing": self.chunks_missing,
            "chunks_dropped": self.chunks_dropped,
            "raw_rms": self.raw_rms_sum / mean_divisor,
            "processed_rms": self.processed_rms_sum / mean_divisor,
            "peak": self.peak_max,
            "clipping_ratio": self.clipping_sum / mean_divisor,
            "gate_active_ratio": self.gate_active_count / mean_divisor,
            "agc_gain": self.agc_gain_sum / mean_divisor,
            "active_channel": self.active_channel_last,
            "telemetry_complete": telemetry_complete,
        }


class CalibrationTelemetryServer:
    """Low-rate TCP diagnostics/control channel for calibration telemetry."""

    def __init__(
        self,
        *,
        bind_host: str,
        port: int,
        telemetry_interval_s: float = 0.25,
    ) -> None:
        self._bind_host = bind_host
        self._port = port
        self._telemetry_interval_s = telemetry_interval_s
        self._shutdown = threading.Event()
        self._thread: threading.Thread | None = None
        self._server_socket: socket.socket | None = None
        self._client_socket: socket.socket | None = None
        self._client_lock = threading.RLock()
        self._outbound: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=200)
        self._state_lock = threading.Lock()
        self._session_id: str | None = None
        self._active_stage: _StageAccumulator | None = None
        self._last_live_emit = 0.0
        self._latest_preview_payload: dict[str, Any] | None = None
        self._recv_buffer = b""

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._shutdown.clear()
        self._thread = threading.Thread(target=self._serve, daemon=True, name="calibration-telemetry-server")
        self._thread.start()

    def stop(self) -> None:
        self._shutdown.set()
        self._close_client()
        if self._server_socket is not None:
            try:
                self._server_socket.close()
            except OSError:
                pass
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    def record_chunk(
        self,
        *,
        sequence_number: int,
        raw_rms: float,
        processed_rms: float,
        peak: float,
        clipping_ratio: float,
        gate_active: bool,
        agc_gain: float,
        active_channel: int,
    ) -> None:
        now = time.monotonic()
        with self._state_lock:
            self._latest_preview_payload = {
                "raw_rms": raw_rms,
                "processed_rms": processed_rms,
                "peak": peak,
                "clipping_ratio": clipping_ratio,
                "gate_active_ratio": 1.0 if gate_active else 0.0,
                "agc_gain": agc_gain,
                "active_channel": active_channel,
                "audio_sequence_start": sequence_number,
                "audio_sequence_end": sequence_number,
                "chunks_captured": 1,
                "chunks_missing": 0,
                "chunks_dropped": 0,
                "connection_state": "connected",
            }
            if self._active_stage is not None:
                self._active_stage.add_chunk(
                    sequence_number=sequence_number,
                    raw_rms=raw_rms,
                    processed_rms=processed_rms,
                    peak=peak,
                    clipping_ratio=clipping_ratio,
                    gate_active=gate_active,
                    agc_gain=agc_gain,
                    active_channel=active_channel,
                )
        if now - self._last_live_emit >= self._telemetry_interval_s:
            self._emit_preview()
            self._last_live_emit = now

    def record_chunk_drop(self, dropped_chunks: int = 1) -> None:
        with self._state_lock:
            if self._active_stage is not None:
                self._active_stage.add_drop(dropped_chunks)

    def _emit_preview(self) -> None:
        with self._state_lock:
            session_id = self._session_id
            payload = dict(self._latest_preview_payload) if self._latest_preview_payload is not None else None
            stage = self._active_stage
            if payload is None:
                return
            if stage is not None:
                payload["session_id"] = stage.session_id
                payload["stage_id"] = stage.stage_id
                payload["stage_type"] = stage.stage_type
            else:
                payload["session_id"] = session_id
        self._queue_outbound(make_telemetry("live_metrics", session_id=session_id, payload=payload))

    def _queue_outbound(self, message: dict[str, Any]) -> None:
        try:
            self._outbound.put_nowait(message)
        except queue.Full:
            try:
                self._outbound.get_nowait()
            except queue.Empty:
                return
            try:
                self._outbound.put_nowait(message)
            except queue.Full:
                return

    def _serve(self) -> None:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self._bind_host, self._port))
        server.listen(1)
        server.settimeout(0.25)
        self._server_socket = server
        while not self._shutdown.is_set():
            if self._client_socket is None:
                try:
                    client, _addr = server.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break
                client.settimeout(0.25)
                with self._client_lock:
                    self._close_client()
                    self._client_socket = client
                    self._recv_buffer = b""
                continue
            self._flush_outbound()
            self._read_request_once()
        self._close_client()

    def _read_request_once(self) -> None:
        client = self._client_socket
        if client is None:
            return
        try:
            data = client.recv(4096)
        except socket.timeout:
            return
        except OSError:
            self._on_disconnect()
            return
        if not data:
            self._on_disconnect()
            return
        self._recv_buffer += data
        while b"\n" in self._recv_buffer:
            raw_line, self._recv_buffer = self._recv_buffer.split(b"\n", 1)
            if not raw_line:
                continue
            try:
                parsed = decode_message(raw_line)
            except ProtocolError as exc:
                self._send(make_error(None, session_id=self._session_id, code="MALFORMED_MESSAGE", message=str(exc)))
                continue
            if parsed.message_type != MESSAGE_REQUEST:
                self._send(make_error(None, session_id=self._session_id, code="INVALID_TYPE", message="Expected request"))
                continue
            self._handle_request(parsed)

    def _handle_request(self, parsed: ParsedMessage) -> None:
        payload = parsed.raw
        action = payload["action"]
        request_id = payload["request_id"]
        session_id = payload.get("session_id")
        request_payload = payload.get("payload", {})

        if action == "ping":
            self._send(make_ack(request_id, session_id=self._session_id, payload={"status": "ok"}))
            return

        if action == "open_session":
            requested = str(request_payload.get("session_id", "")).strip()
            if not requested:
                self._send(make_error(request_id, session_id=None, code="INVALID_SESSION", message="session_id is required"))
                return
            with self._state_lock:
                if self._session_id and self._session_id != requested:
                    self._send(
                        make_error(
                            request_id,
                            session_id=self._session_id,
                            code="SESSION_OWNED",
                            message="Another calibration session is already active",
                        )
                    )
                    return
                self._session_id = requested
                self._active_stage = None
            self._send(make_ack(request_id, session_id=requested, payload={"session_id": requested}))
            return

        with self._state_lock:
            if not self._session_id or session_id != self._session_id:
                self._send(
                    make_error(
                        request_id,
                        session_id=self._session_id,
                        code="SESSION_MISMATCH",
                        message="session_id does not match active calibration session",
                    )
                )
                return

        if action == "cancel_session":
            with self._state_lock:
                self._active_stage = None
                self._session_id = None
            self._send(make_ack(request_id, session_id=None, payload={"cancelled": True}))
            return

        if action == "close_session":
            with self._state_lock:
                self._active_stage = None
                closed_session = self._session_id
                self._session_id = None
            self._send(make_ack(request_id, session_id=None, payload={"closed_session_id": closed_session}))
            return

        if action == "open_stage":
            stage_id = str(request_payload.get("stage_id", "")).strip()
            stage_type = str(request_payload.get("stage_type", "")).strip()
            if not stage_id or not stage_type:
                self._send(
                    make_error(
                        request_id,
                        session_id=self._session_id,
                        code="INVALID_STAGE",
                        message="stage_id and stage_type are required",
                    )
                )
                return
            with self._state_lock:
                self._active_stage = _StageAccumulator(
                    session_id=self._session_id or "",
                    stage_id=stage_id,
                    stage_type=stage_type,
                    start_timestamp_ms=int(time.time() * 1000),
                )
            self._send(make_ack(request_id, session_id=self._session_id, payload={"stage_id": stage_id, "opened": True}))
            return

        if action == "close_stage":
            stage_id = str(request_payload.get("stage_id", "")).strip()
            with self._state_lock:
                if self._active_stage is None or self._active_stage.stage_id != stage_id:
                    self._send(
                        make_error(
                            request_id,
                            session_id=self._session_id,
                            code="STAGE_MISMATCH",
                            message="No matching active stage to close",
                        )
                    )
                    return
                stage_summary = self._active_stage.summary(int(time.time() * 1000))
                self._active_stage = None
            self._send(make_ack(request_id, session_id=self._session_id, payload={"stage_summary": stage_summary}))
            return

        self._send(make_error(request_id, session_id=self._session_id, code="UNSUPPORTED_ACTION", message=action))

    def _send(self, message: dict[str, Any]) -> None:
        client = self._client_socket
        if client is None:
            return
        try:
            client.sendall(encode_message(message))
        except OSError:
            self._on_disconnect()

    def _flush_outbound(self) -> None:
        client = self._client_socket
        if client is None:
            return
        while True:
            try:
                message = self._outbound.get_nowait()
            except queue.Empty:
                return
            try:
                client.sendall(encode_message(message))
            except OSError:
                self._on_disconnect()
                return

    def _on_disconnect(self) -> None:
        self._close_client()
        self._recv_buffer = b""
        with self._state_lock:
            self._active_stage = None
            self._session_id = None

    def _close_client(self) -> None:
        with self._client_lock:
            if self._client_socket is not None:
                try:
                    self._client_socket.close()
                except OSError:
                    pass
                self._client_socket = None
