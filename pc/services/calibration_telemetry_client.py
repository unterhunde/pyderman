"""TCP client for calibration diagnostics/control and live telemetry messages."""

from __future__ import annotations

import socket
import threading
from collections import deque
from dataclasses import dataclass
from typing import Any

from calibration_protocol import (
    MESSAGE_ACK,
    MESSAGE_ERROR,
    MESSAGE_TELEMETRY,
    ProtocolError,
    decode_message,
    encode_message,
    make_request,
)


class TelemetryTransportError(RuntimeError):
    """Raised when diagnostics/control transport is unavailable or disconnected."""


class TelemetryRequestError(RuntimeError):
    """Raised when a diagnostics/control request fails or times out."""


@dataclass
class _PendingRequest:
    event: threading.Event
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None


class CalibrationTelemetryClient:
    def __init__(self, *, host: str, port: int) -> None:
        self._host = host
        self._port = port
        self._socket: socket.socket | None = None
        self._receiver_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._recv_buffer = b""
        self._pending_lock = threading.Lock()
        self._pending: dict[str, _PendingRequest] = {}
        self._telemetry_lock = threading.Lock()
        self._telemetry: deque[dict[str, Any]] = deque(maxlen=500)
        self._connection_state = "disconnected"
        self._last_error = ""
        self._send_lock = threading.Lock()

    @property
    def connection_state(self) -> str:
        return self._connection_state

    @property
    def last_error(self) -> str:
        return self._last_error

    def connect(self, *, timeout_s: float = 3.0) -> None:
        if self._socket is not None:
            return
        sock = socket.create_connection((self._host, self._port), timeout=timeout_s)
        sock.settimeout(0.25)
        self._socket = sock
        self._stop_event.clear()
        self._connection_state = "connected"
        self._last_error = ""
        self._receiver_thread = threading.Thread(target=self._receiver_loop, daemon=True, name="calibration-telemetry-client")
        self._receiver_thread.start()

    def disconnect(self) -> None:
        self._stop_event.set()
        if self._socket is not None:
            try:
                self._socket.close()
            except OSError:
                pass
            self._socket = None
        if self._receiver_thread is not None:
            self._receiver_thread.join(timeout=1.5)
            self._receiver_thread = None
        self._connection_state = "disconnected"
        with self._pending_lock:
            for pending in self._pending.values():
                pending.error = {"code": "DISCONNECTED", "message": "Diagnostics channel disconnected"}
                pending.event.set()
            self._pending.clear()

    def send_request(
        self,
        *,
        action: str,
        session_id: str | None,
        payload: dict[str, Any],
        timeout_s: float = 3.0,
    ) -> dict[str, Any]:
        sock = self._socket
        if sock is None:
            raise TelemetryTransportError("Diagnostics channel is not connected")
        request = make_request(action, session_id=session_id, payload=payload)
        request_id = request["request_id"]
        pending = _PendingRequest(event=threading.Event())
        with self._pending_lock:
            self._pending[request_id] = pending
        try:
            with self._send_lock:
                sock.sendall(encode_message(request))
        except OSError as exc:
            with self._pending_lock:
                self._pending.pop(request_id, None)
            self._connection_state = "disconnected"
            raise TelemetryTransportError(f"Failed to send diagnostics request '{action}': {exc}") from exc

        if not pending.event.wait(timeout_s):
            with self._pending_lock:
                self._pending.pop(request_id, None)
            raise TelemetryRequestError(f"Timed out waiting for '{action}' acknowledgement")
        if pending.error is not None:
            code = pending.error.get("code", "UNKNOWN")
            message = pending.error.get("message", "unknown error")
            raise TelemetryRequestError(f"{action} failed [{code}]: {message}")
        if pending.result is None:
            raise TelemetryRequestError(f"{action} failed: missing acknowledgement payload")
        return pending.result

    def read_live_telemetry(self) -> list[dict[str, Any]]:
        with self._telemetry_lock:
            items = list(self._telemetry)
            self._telemetry.clear()
        return items

    def _receiver_loop(self) -> None:
        while not self._stop_event.is_set():
            sock = self._socket
            if sock is None:
                return
            try:
                data = sock.recv(4096)
            except socket.timeout:
                continue
            except OSError as exc:
                self._mark_disconnected(str(exc))
                return
            if not data:
                self._mark_disconnected("diagnostics connection closed by peer")
                return

            self._recv_buffer += data
            while b"\n" in self._recv_buffer:
                raw_line, self._recv_buffer = self._recv_buffer.split(b"\n", 1)
                if not raw_line:
                    continue
                try:
                    parsed = decode_message(raw_line)
                except ProtocolError as exc:
                    self._last_error = str(exc)
                    continue
                self._handle_message(parsed.raw)

    def _handle_message(self, message: dict[str, Any]) -> None:
        message_type = message["message_type"]
        if message_type in {MESSAGE_ACK, MESSAGE_ERROR}:
            request_id = message.get("request_id")
            if not request_id:
                return
            with self._pending_lock:
                pending = self._pending.pop(request_id, None)
            if pending is None:
                return
            if message_type == MESSAGE_ACK:
                pending.result = message.get("payload", {})
            else:
                pending.error = message.get("error", {"code": "UNKNOWN", "message": "unknown error"})
            pending.event.set()
            return
        if message_type == MESSAGE_TELEMETRY:
            with self._telemetry_lock:
                self._telemetry.append(message)

    def _mark_disconnected(self, error_message: str) -> None:
        self._last_error = error_message
        self._connection_state = "disconnected"
        with self._pending_lock:
            pending_items = list(self._pending.values())
            self._pending.clear()
        for pending in pending_items:
            pending.error = {"code": "DISCONNECTED", "message": error_message}
            pending.event.set()
