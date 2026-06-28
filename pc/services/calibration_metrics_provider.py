"""Calibration metrics provider interfaces, simulation provider, and live telemetry provider."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Protocol

from pc.services.calibration_telemetry_aggregation import (
    StageValidationResult,
    validate_live_metrics_payload,
    validate_stage_summary,
)
from pc.services.calibration_telemetry_client import (
    CalibrationTelemetryClient,
    TelemetryRequestError,
    TelemetryTransportError,
)


class MeasurementStage(str, Enum):
    SILENCE = "silence"
    NORMAL = "normal"
    LOUD = "loud"
    PHRASE = "phrase"


@dataclass(frozen=True)
class StageMetrics:
    raw_rms: float
    processed_rms: float
    peak: float
    clipping: float
    gate_ratio: float
    agc_gain: float
    capture_success: bool
    active_channel: int = 0
    chunks_captured: int = 0
    chunks_missing: int = 0
    chunks_dropped: int = 0
    audio_sequence_start: int | None = None
    audio_sequence_end: int | None = None
    stage_id: str = ""
    session_id: str = ""
    stage_type: str = ""
    start_timestamp_ms: int = 0
    end_timestamp_ms: int = 0
    telemetry_complete: bool = False
    failure_reason: str = ""
    telemetry_connection_state: str = "unknown"


@dataclass(frozen=True)
class CalibrationProviderMetadata:
    mode: str
    source_label: str
    is_simulated: bool
    simulation_warning: str


class CalibrationMetricsProvider(Protocol):
    def metadata(self) -> CalibrationProviderMetadata:
        """Describe provider source/mode/capability metadata for UI labeling."""

    def start_session(self, *, session_id: str, generation: int) -> None:
        """Start provider-side state for one calibration session."""

    def end_session(self, *, session_id: str, cancelled: bool) -> None:
        """End provider-side state for one calibration session."""

    def start_stage(self, *, session_id: str, stage_id: str, stage: MeasurementStage) -> None:
        """Open one synchronized stage capture window."""

    def finish_stage(
        self,
        *,
        session_id: str,
        stage_id: str,
        stage: MeasurementStage,
        timeout_seconds: float,
    ) -> StageMetrics:
        """Close one synchronized stage capture window and return aggregate summary."""

    def poll_live_metrics(self, *, session_id: str) -> StageMetrics | None:
        """Return latest rolling live metrics for preview/capture display."""

    def connection_state(self) -> str:
        """Return diagnostics channel state for operator display."""


class SimulatedCalibrationMetricsProvider:
    """Deterministic provider used to validate controller/view behavior."""

    _BASELINES: dict[MeasurementStage, StageMetrics] = {
        MeasurementStage.SILENCE: StageMetrics(0.003, 0.001, 0.015, 0.0, 0.92, 1.05, True, telemetry_complete=True),
        MeasurementStage.NORMAL: StageMetrics(0.045, 0.036, 0.32, 0.0, 0.22, 1.20, True, telemetry_complete=True),
        MeasurementStage.LOUD: StageMetrics(0.090, 0.072, 0.58, 0.01, 0.10, 1.12, True, telemetry_complete=True),
        MeasurementStage.PHRASE: StageMetrics(0.060, 0.050, 0.44, 0.0, 0.15, 1.17, True, telemetry_complete=True),
    }

    def __init__(self, failed_attempts: dict[MeasurementStage, set[int]] | None = None) -> None:
        self._failed_attempts = failed_attempts or {}
        self._active_session_id: str | None = None

    def metadata(self) -> CalibrationProviderMetadata:
        return CalibrationProviderMetadata(
            mode="simulation",
            source_label="deterministic-simulated-provider",
            is_simulated=True,
            simulation_warning=(
                "SIMULATION MODE — Results are test data and are not production microphone calibration values."
            ),
        )

    def capture(self, stage: MeasurementStage, attempt: int, capture_seconds: int) -> StageMetrics:
        """Backward-compatible Phase A helper used by existing regression tests."""
        base = self._BASELINES[stage]
        delta = 0.001 * max(attempt - 1, 0)
        clip_delta = 0.002 * max(attempt - 1, 0)
        gate_delta = 0.01 * max(attempt - 1, 0)
        gain_delta = 0.01 * max(attempt - 1, 0)
        success = base.capture_success and capture_seconds > 0 and attempt not in self._failed_attempts.get(stage, set())
        now_ms = int(time.time() * 1000)
        return StageMetrics(
            raw_rms=base.raw_rms + delta,
            processed_rms=base.processed_rms + delta,
            peak=min(1.0, base.peak + 0.01 * max(attempt - 1, 0)),
            clipping=min(1.0, base.clipping + clip_delta),
            gate_ratio=min(1.0, base.gate_ratio + gate_delta),
            agc_gain=base.agc_gain + gain_delta,
            capture_success=success,
            active_channel=0,
            chunks_captured=8,
            chunks_missing=0,
            chunks_dropped=0,
            audio_sequence_start=1000 + attempt * 10,
            audio_sequence_end=1007 + attempt * 10,
            stage_id=f"{stage.value}-{attempt}",
            session_id="",
            stage_type=stage.value,
            start_timestamp_ms=now_ms - 1000,
            end_timestamp_ms=now_ms,
            telemetry_complete=success,
            failure_reason="" if success else f"simulated capture failure for {stage.value}",
            telemetry_connection_state="simulated",
        )

    def start_session(self, *, session_id: str, generation: int) -> None:
        self._active_session_id = session_id

    def end_session(self, *, session_id: str, cancelled: bool) -> None:
        if self._active_session_id == session_id:
            self._active_session_id = None

    def start_stage(self, *, session_id: str, stage_id: str, stage: MeasurementStage) -> None:
        if self._active_session_id != session_id:
            raise RuntimeError("simulation session mismatch")

    def finish_stage(
        self,
        *,
        session_id: str,
        stage_id: str,
        stage: MeasurementStage,
        timeout_seconds: float,
    ) -> StageMetrics:
        if self._active_session_id != session_id:
            return StageMetrics(0, 0, 0, 0, 0, 0, False, failure_reason="stale simulation session", telemetry_complete=False)
        attempt = int(stage_id.rsplit("-", 1)[-1]) if "-" in stage_id else 1
        base = self._BASELINES[stage]
        delta = 0.001 * max(attempt - 1, 0)
        clip_delta = 0.002 * max(attempt - 1, 0)
        gate_delta = 0.01 * max(attempt - 1, 0)
        gain_delta = 0.01 * max(attempt - 1, 0)
        should_fail = attempt in self._failed_attempts.get(stage, set())
        success = base.capture_success and not should_fail and timeout_seconds > 0
        now_ms = int(time.time() * 1000)
        return StageMetrics(
            raw_rms=base.raw_rms + delta,
            processed_rms=base.processed_rms + delta,
            peak=min(1.0, base.peak + 0.01 * max(attempt - 1, 0)),
            clipping=min(1.0, base.clipping + clip_delta),
            gate_ratio=min(1.0, base.gate_ratio + gate_delta),
            agc_gain=base.agc_gain + gain_delta,
            capture_success=success,
            active_channel=0,
            chunks_captured=8,
            chunks_missing=0,
            chunks_dropped=0,
            audio_sequence_start=1000 + attempt * 10,
            audio_sequence_end=1007 + attempt * 10,
            stage_id=stage_id,
            session_id=session_id,
            stage_type=stage.value,
            start_timestamp_ms=now_ms - 1000,
            end_timestamp_ms=now_ms,
            telemetry_complete=success,
            failure_reason="" if success else f"simulated capture failure for {stage.value}",
            telemetry_connection_state="simulated",
        )

    def poll_live_metrics(self, *, session_id: str) -> StageMetrics | None:
        if self._active_session_id != session_id:
            return None
        return StageMetrics(
            raw_rms=0.032,
            processed_rms=0.026,
            peak=0.21,
            clipping=0.0,
            gate_ratio=0.25,
            agc_gain=1.18,
            capture_success=True,
            active_channel=0,
            chunks_captured=1,
            chunks_missing=0,
            chunks_dropped=0,
            audio_sequence_start=0,
            audio_sequence_end=0,
            telemetry_complete=True,
            telemetry_connection_state="simulated",
        )

    def connection_state(self) -> str:
        return "simulated"


class LiveTelemetryCalibrationMetricsProvider:
    """Provider backed by Pi diagnostics/control telemetry."""

    def __init__(
        self,
        *,
        pi_host: str,
        diagnostics_port: int,
        client_factory: Callable[[str, int], CalibrationTelemetryClient] | None = None,
    ) -> None:
        self._pi_host = pi_host
        self._diagnostics_port = diagnostics_port
        factory = client_factory or (lambda host, port: CalibrationTelemetryClient(host=host, port=port))
        self._client = factory(pi_host, diagnostics_port)
        self._active_session_id: str | None = None
        self._active_generation: int | None = None
        self._latest_live_metrics: StageMetrics | None = None

    def metadata(self) -> CalibrationProviderMetadata:
        return CalibrationProviderMetadata(
            mode="live_telemetry",
            source_label=f"pi:{self._pi_host}:{self._diagnostics_port}",
            is_simulated=False,
            simulation_warning="",
        )

    def start_session(self, *, session_id: str, generation: int) -> None:
        self._client.connect(timeout_s=3.0)
        self._client.send_request(
            action="open_session",
            session_id=session_id,
            payload={"session_id": session_id, "generation": generation},
            timeout_s=3.0,
        )
        self._active_session_id = session_id
        self._active_generation = generation

    def end_session(self, *, session_id: str, cancelled: bool) -> None:
        if self._active_session_id != session_id:
            return
        action = "cancel_session" if cancelled else "close_session"
        try:
            self._client.send_request(
                action=action,
                session_id=session_id,
                payload={"session_id": session_id},
                timeout_s=2.0,
            )
        except (TelemetryTransportError, TelemetryRequestError):
            pass
        finally:
            self._client.disconnect()
            self._active_session_id = None
            self._active_generation = None
            self._latest_live_metrics = None

    def start_stage(self, *, session_id: str, stage_id: str, stage: MeasurementStage) -> None:
        if self._active_session_id != session_id:
            raise RuntimeError("stale or mismatched session for live telemetry stage start")
        self._client.send_request(
            action="open_stage",
            session_id=session_id,
            payload={"stage_id": stage_id, "stage_type": stage.value},
            timeout_s=2.5,
        )

    def finish_stage(
        self,
        *,
        session_id: str,
        stage_id: str,
        stage: MeasurementStage,
        timeout_seconds: float,
    ) -> StageMetrics:
        if self._active_session_id != session_id:
            return StageMetrics(0, 0, 0, 0, 0, 0, False, failure_reason="stale session", telemetry_complete=False)
        try:
            response = self._client.send_request(
                action="close_stage",
                session_id=session_id,
                payload={"stage_id": stage_id},
                timeout_s=max(2.0, timeout_seconds),
            )
        except (TelemetryTransportError, TelemetryRequestError) as exc:
            return StageMetrics(
                0,
                0,
                0,
                0,
                0,
                0,
                False,
                stage_id=stage_id,
                session_id=session_id,
                stage_type=stage.value,
                telemetry_complete=False,
                failure_reason=str(exc),
                telemetry_connection_state=self.connection_state(),
            )
        summary = response.get("stage_summary")
        if not isinstance(summary, dict):
            return StageMetrics(
                0,
                0,
                0,
                0,
                0,
                0,
                False,
                stage_id=stage_id,
                session_id=session_id,
                stage_type=stage.value,
                telemetry_complete=False,
                failure_reason="missing stage summary",
                telemetry_connection_state=self.connection_state(),
            )
        validation: StageValidationResult = validate_stage_summary(
            summary,
            expected_session_id=session_id,
            expected_stage_id=stage_id,
            expected_stage_type=stage.value,
        )
        if not validation.complete:
            return StageMetrics(
                raw_rms=float(summary.get("raw_rms", 0.0)),
                processed_rms=float(summary.get("processed_rms", 0.0)),
                peak=float(summary.get("peak", 0.0)),
                clipping=float(summary.get("clipping_ratio", 0.0)),
                gate_ratio=float(summary.get("gate_active_ratio", 0.0)),
                agc_gain=float(summary.get("agc_gain", 0.0)),
                capture_success=False,
                active_channel=int(summary.get("active_channel", 0)),
                chunks_captured=int(summary.get("chunks_captured", 0)),
                chunks_missing=int(summary.get("chunks_missing", 0)),
                chunks_dropped=int(summary.get("chunks_dropped", 0)),
                audio_sequence_start=summary.get("audio_sequence_start"),
                audio_sequence_end=summary.get("audio_sequence_end"),
                stage_id=stage_id,
                session_id=session_id,
                stage_type=stage.value,
                start_timestamp_ms=int(summary.get("start_timestamp_ms", 0)),
                end_timestamp_ms=int(summary.get("end_timestamp_ms", 0)),
                telemetry_complete=bool(summary.get("telemetry_complete", False)),
                failure_reason=validation.reason,
                telemetry_connection_state=self.connection_state(),
            )
        return StageMetrics(
            raw_rms=float(summary["raw_rms"]),
            processed_rms=float(summary["processed_rms"]),
            peak=float(summary["peak"]),
            clipping=float(summary["clipping_ratio"]),
            gate_ratio=float(summary["gate_active_ratio"]),
            agc_gain=float(summary["agc_gain"]),
            capture_success=True,
            active_channel=int(summary["active_channel"]),
            chunks_captured=int(summary["chunks_captured"]),
            chunks_missing=int(summary["chunks_missing"]),
            chunks_dropped=int(summary["chunks_dropped"]),
            audio_sequence_start=int(summary["audio_sequence_start"]),
            audio_sequence_end=int(summary["audio_sequence_end"]),
            stage_id=stage_id,
            session_id=session_id,
            stage_type=stage.value,
            start_timestamp_ms=int(summary["start_timestamp_ms"]),
            end_timestamp_ms=int(summary["end_timestamp_ms"]),
            telemetry_complete=bool(summary["telemetry_complete"]),
            failure_reason="",
            telemetry_connection_state=self.connection_state(),
        )

    def poll_live_metrics(self, *, session_id: str) -> StageMetrics | None:
        if session_id != self._active_session_id:
            return None
        for message in self._client.read_live_telemetry():
            payload = message.get("payload")
            message_session_id = message.get("session_id")
            if message_session_id not in {None, session_id}:
                continue
            if not isinstance(payload, dict):
                continue
            try:
                validate_live_metrics_payload(payload)
            except Exception:  # noqa: BLE001
                continue
            self._latest_live_metrics = StageMetrics(
                raw_rms=float(payload["raw_rms"]),
                processed_rms=float(payload["processed_rms"]),
                peak=float(payload["peak"]),
                clipping=float(payload["clipping_ratio"]),
                gate_ratio=float(payload["gate_active_ratio"]),
                agc_gain=float(payload["agc_gain"]),
                capture_success=True,
                active_channel=int(payload["active_channel"]),
                chunks_captured=int(payload["chunks_captured"]),
                chunks_missing=int(payload["chunks_missing"]),
                chunks_dropped=int(payload["chunks_dropped"]),
                audio_sequence_start=int(payload["audio_sequence_start"]),
                audio_sequence_end=int(payload["audio_sequence_end"]),
                stage_id=str(payload.get("stage_id", "")),
                session_id=session_id,
                stage_type=str(payload.get("stage_type", "")),
                telemetry_complete=True,
                telemetry_connection_state=self.connection_state(),
            )
        return self._latest_live_metrics

    def connection_state(self) -> str:
        return self._client.connection_state


def new_calibration_session_id() -> str:
    return f"cal-{uuid.uuid4()}"
