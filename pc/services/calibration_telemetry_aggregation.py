"""Validation and mapping helpers for calibration telemetry payloads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class TelemetryValidationError(ValueError):
    """Raised when telemetry payloads are missing required fields or are inconsistent."""


@dataclass(frozen=True)
class StageValidationResult:
    complete: bool
    reason: str


_REQUIRED_STAGE_FIELDS = (
    "session_id",
    "stage_id",
    "stage_type",
    "start_timestamp_ms",
    "end_timestamp_ms",
    "audio_sequence_start",
    "audio_sequence_end",
    "chunks_captured",
    "chunks_missing",
    "chunks_dropped",
    "raw_rms",
    "processed_rms",
    "peak",
    "clipping_ratio",
    "gate_active_ratio",
    "agc_gain",
    "active_channel",
    "telemetry_complete",
)


def validate_stage_summary(
    summary: dict[str, Any],
    *,
    expected_session_id: str,
    expected_stage_id: str,
    expected_stage_type: str,
) -> StageValidationResult:
    missing = [field for field in _REQUIRED_STAGE_FIELDS if field not in summary]
    if missing:
        return StageValidationResult(False, f"missing required telemetry fields: {', '.join(missing)}")
    if summary["session_id"] != expected_session_id:
        return StageValidationResult(False, "session mismatch in stage summary")
    if summary["stage_id"] != expected_stage_id:
        return StageValidationResult(False, "stage mismatch in stage summary")
    if summary["stage_type"] != expected_stage_type:
        return StageValidationResult(False, "stage type mismatch in stage summary")
    if summary["audio_sequence_start"] is None or summary["audio_sequence_end"] is None:
        return StageValidationResult(False, "missing sequence range in stage summary")
    if int(summary["audio_sequence_end"]) < int(summary["audio_sequence_start"]):
        return StageValidationResult(False, "invalid sequence range in stage summary")
    if int(summary["chunks_captured"]) <= 0:
        return StageValidationResult(False, "no telemetry chunks captured for stage")
    if not bool(summary["telemetry_complete"]):
        return StageValidationResult(False, "stage telemetry marked incomplete by Pi")
    return StageValidationResult(True, "")


def validate_live_metrics_payload(payload: dict[str, Any]) -> None:
    required = (
        "raw_rms",
        "processed_rms",
        "peak",
        "clipping_ratio",
        "gate_active_ratio",
        "agc_gain",
        "active_channel",
        "audio_sequence_start",
        "audio_sequence_end",
        "chunks_captured",
        "chunks_missing",
        "chunks_dropped",
    )
    missing = [field for field in required if field not in payload]
    if missing:
        raise TelemetryValidationError(f"live telemetry missing fields: {', '.join(missing)}")
