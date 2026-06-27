"""Calibration metrics provider interfaces and deterministic simulation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


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


@dataclass(frozen=True)
class CalibrationProviderMetadata:
    mode: str
    source_label: str
    is_simulated: bool
    simulation_warning: str


class CalibrationMetricsProvider(Protocol):
    def metadata(self) -> CalibrationProviderMetadata:
        """Describe provider source/mode/capability metadata for UI labeling."""

    def capture(self, stage: MeasurementStage, attempt: int, capture_seconds: int) -> StageMetrics:
        """Capture one deterministic metrics window for a wizard stage."""


class SimulatedCalibrationMetricsProvider:
    """Deterministic provider used to validate controller/view behavior."""

    _BASELINES: dict[MeasurementStage, StageMetrics] = {
        MeasurementStage.SILENCE: StageMetrics(0.003, 0.001, 0.015, 0.0, 0.92, 1.05, True),
        MeasurementStage.NORMAL: StageMetrics(0.045, 0.036, 0.32, 0.0, 0.22, 1.20, True),
        MeasurementStage.LOUD: StageMetrics(0.090, 0.072, 0.58, 0.01, 0.10, 1.12, True),
        MeasurementStage.PHRASE: StageMetrics(0.060, 0.050, 0.44, 0.0, 0.15, 1.17, True),
    }

    def __init__(self, failed_attempts: dict[MeasurementStage, set[int]] | None = None) -> None:
        self._failed_attempts = failed_attempts or {}

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
        base = self._BASELINES[stage]
        delta = 0.001 * max(attempt - 1, 0)
        clip_delta = 0.002 * max(attempt - 1, 0)
        gate_delta = 0.01 * max(attempt - 1, 0)
        gain_delta = 0.01 * max(attempt - 1, 0)
        should_fail = attempt in self._failed_attempts.get(stage, set())
        success = base.capture_success and not should_fail and capture_seconds > 0
        return StageMetrics(
            raw_rms=base.raw_rms + delta,
            processed_rms=base.processed_rms + delta,
            peak=min(1.0, base.peak + 0.01 * max(attempt - 1, 0)),
            clipping=min(1.0, base.clipping + clip_delta),
            gate_ratio=min(1.0, base.gate_ratio + gate_delta),
            agc_gain=base.agc_gain + gain_delta,
            capture_success=success,
        )
