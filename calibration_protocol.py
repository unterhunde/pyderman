"""Versioned diagnostics/control protocol for calibration telemetry."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from typing import Any

SCHEMA_VERSION = "calibration.v1"

MESSAGE_REQUEST = "request"
MESSAGE_ACK = "ack"
MESSAGE_ERROR = "error"
MESSAGE_TELEMETRY = "telemetry"


class ProtocolError(ValueError):
    """Raised when a message is malformed or violates protocol requirements."""


@dataclass(frozen=True)
class ParsedMessage:
    raw: dict[str, Any]
    message_type: str
    schema_version: str


def make_request(action: str, *, session_id: str | None, payload: dict[str, Any]) -> dict[str, Any]:
    request_id = str(uuid.uuid4())
    return {
        "schema_version": SCHEMA_VERSION,
        "message_type": MESSAGE_REQUEST,
        "request_id": request_id,
        "timestamp_ms": int(time.time() * 1000),
        "action": action,
        "session_id": session_id,
        "payload": payload,
    }


def make_ack(request_id: str, *, session_id: str | None, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "message_type": MESSAGE_ACK,
        "request_id": request_id,
        "timestamp_ms": int(time.time() * 1000),
        "session_id": session_id,
        "payload": payload,
    }


def make_error(
    request_id: str | None,
    *,
    session_id: str | None,
    code: str,
    message: str,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "message_type": MESSAGE_ERROR,
        "request_id": request_id,
        "timestamp_ms": int(time.time() * 1000),
        "session_id": session_id,
        "error": {"code": code, "message": message},
    }


def make_telemetry(
    telemetry_type: str,
    *,
    session_id: str | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "message_type": MESSAGE_TELEMETRY,
        "timestamp_ms": int(time.time() * 1000),
        "session_id": session_id,
        "telemetry_type": telemetry_type,
        "payload": payload,
    }


def parse_message_dict(data: dict[str, Any]) -> ParsedMessage:
    schema_version = data.get("schema_version")
    if schema_version != SCHEMA_VERSION:
        raise ProtocolError(f"Unsupported schema_version '{schema_version}'")
    message_type = data.get("message_type")
    if message_type not in {MESSAGE_REQUEST, MESSAGE_ACK, MESSAGE_ERROR, MESSAGE_TELEMETRY}:
        raise ProtocolError(f"Unsupported message_type '{message_type}'")

    if message_type == MESSAGE_REQUEST:
        _require_fields(data, "request", ("request_id", "action", "payload"))
    elif message_type == MESSAGE_ACK:
        _require_fields(data, "ack", ("request_id", "payload"))
    elif message_type == MESSAGE_ERROR:
        _require_fields(data, "error", ("error",))
        error = data["error"]
        if not isinstance(error, dict) or "code" not in error or "message" not in error:
            raise ProtocolError("error message must include error.code and error.message")
    elif message_type == MESSAGE_TELEMETRY:
        _require_fields(data, "telemetry", ("telemetry_type", "payload"))

    return ParsedMessage(raw=data, message_type=message_type, schema_version=schema_version)


def _require_fields(message: dict[str, Any], message_kind: str, fields: tuple[str, ...]) -> None:
    missing = [field for field in fields if field not in message]
    if missing:
        raise ProtocolError(f"{message_kind} missing required fields: {', '.join(missing)}")


def encode_message(message: dict[str, Any]) -> bytes:
    return (json.dumps(message, separators=(",", ":")) + "\n").encode("utf-8")


def decode_message(raw_line: bytes) -> ParsedMessage:
    try:
        payload = json.loads(raw_line.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise ProtocolError(f"Invalid JSON payload: {exc}") from exc
    if not isinstance(payload, dict):
        raise ProtocolError("Decoded message is not a JSON object")
    return parse_message_dict(payload)

