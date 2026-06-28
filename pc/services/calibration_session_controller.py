"""State-machine controller for the microphone calibration wizard."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Protocol

from pc.services.calibration_metrics_provider import (
    CalibrationMetricsProvider,
    CalibrationProviderMetadata,
    MeasurementStage,
    StageMetrics,
    new_calibration_session_id,
)


class CalibrationWizardState(str, Enum):
    IDLE = "IDLE"
    VERIFYING = "VERIFYING"
    PREVIEW = "PREVIEW"
    PREPARE_SILENCE = "PREPARE_SILENCE"
    CAPTURE_SILENCE = "CAPTURE_SILENCE"
    PREPARE_NORMAL = "PREPARE_NORMAL"
    CAPTURE_NORMAL = "CAPTURE_NORMAL"
    PREPARE_LOUD = "PREPARE_LOUD"
    CAPTURE_LOUD = "CAPTURE_LOUD"
    PREPARE_PHRASE = "PREPARE_PHRASE"
    CAPTURE_PHRASE = "CAPTURE_PHRASE"
    COMPARE = "COMPARE"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class InvalidTransitionError(RuntimeError):
    pass


class WizardScheduler(Protocol):
    def call_later(self, delay_ms: int, callback: Callable[[], None]) -> object:
        ...

    def cancel(self, handle: object) -> None:
        ...


@dataclass(frozen=True)
class CalibrationWizardViewState:
    state: CalibrationWizardState
    stage_name: str
    instruction: str
    cue: str
    countdown_seconds: int
    progress_current: int
    progress_total: int
    can_start: bool
    can_repeat: bool
    can_next: bool
    can_cancel: bool
    can_close: bool
    phrase_enabled: bool
    status_message: str
    stage_results: dict[MeasurementStage, StageMetrics]
    latest_metrics: StageMetrics | None
    provider_mode: str
    provider_source_label: str
    simulation_mode: bool
    simulation_warning: str
    telemetry_connection_state: str
    session_id: str


_PREPARE_STATE_BY_STAGE = {
    MeasurementStage.SILENCE: CalibrationWizardState.PREPARE_SILENCE,
    MeasurementStage.NORMAL: CalibrationWizardState.PREPARE_NORMAL,
    MeasurementStage.LOUD: CalibrationWizardState.PREPARE_LOUD,
    MeasurementStage.PHRASE: CalibrationWizardState.PREPARE_PHRASE,
}

_CAPTURE_STATE_BY_STAGE = {
    MeasurementStage.SILENCE: CalibrationWizardState.CAPTURE_SILENCE,
    MeasurementStage.NORMAL: CalibrationWizardState.CAPTURE_NORMAL,
    MeasurementStage.LOUD: CalibrationWizardState.CAPTURE_LOUD,
    MeasurementStage.PHRASE: CalibrationWizardState.CAPTURE_PHRASE,
}

_STAGE_BY_PREPARE_STATE = {state: stage for stage, state in _PREPARE_STATE_BY_STAGE.items()}
_STAGE_BY_CAPTURE_STATE = {state: stage for stage, state in _CAPTURE_STATE_BY_STAGE.items()}


class CalibrationSessionController:
    def __init__(
        self,
        metrics_provider: CalibrationMetricsProvider,
        scheduler: WizardScheduler,
        on_update: Callable[[CalibrationWizardViewState], None],
        *,
        prepare_seconds: int = 3,
        capture_seconds: int = 4,
        phrase_enabled: bool = True,
    ) -> None:
        self._metrics_provider = metrics_provider
        self._provider_metadata: CalibrationProviderMetadata = metrics_provider.metadata()
        self._scheduler = scheduler
        self._on_update = on_update
        self._prepare_seconds = prepare_seconds
        self._capture_seconds = capture_seconds
        self._default_phrase_enabled = phrase_enabled

        self._state = CalibrationWizardState.IDLE
        self._generation = 0
        self._pending_handles: list[object] = []
        self._countdown_seconds = 0
        self._cue = "idle"
        self._status_message = "Ready to start microphone calibration."
        self._phrase_enabled = phrase_enabled
        self._active_stage: MeasurementStage | None = None
        self._active_stage_id: str = ""
        self._session_id: str = ""
        self._latest_metrics: StageMetrics | None = None
        self._stage_results: dict[MeasurementStage, StageMetrics] = {}
        self._stage_attempts: dict[MeasurementStage, int] = {}
        self._stage_capture_complete = False
        self._stage_capture_success = False
        self._publish()

    def start_wizard(self, *, phrase_enabled: bool | None = None) -> None:
        if self._state not in {
            CalibrationWizardState.IDLE,
            CalibrationWizardState.COMPLETE,
            CalibrationWizardState.FAILED,
            CalibrationWizardState.CANCELLED,
        }:
            raise InvalidTransitionError(f"Cannot start wizard from {self._state.value}")
        self._end_provider_session(cancelled=True)
        self._invalidate_pending_callbacks()
        self._generation += 1
        self._session_id = new_calibration_session_id()
        self._phrase_enabled = self._default_phrase_enabled if phrase_enabled is None else phrase_enabled
        self._active_stage = None
        self._active_stage_id = ""
        self._latest_metrics = None
        self._stage_results.clear()
        self._stage_attempts.clear()
        self._stage_capture_complete = False
        self._stage_capture_success = False
        try:
            self._metrics_provider.start_session(session_id=self._session_id, generation=self._generation)
        except Exception as exc:
            self._set_state(
                CalibrationWizardState.FAILED,
                cue="stop",
                message=f"Failed to start calibration session: {exc}",
            )
            return
        mode_text = "simulation mode" if self._provider_metadata.is_simulated else "live telemetry mode"
        self._set_state(
            CalibrationWizardState.VERIFYING,
            cue="prepare",
            message=f"Verify connection and microphone availability, then click Next ({mode_text}).",
        )
        self._schedule_live_poll(self._generation)

    def start_stage(self) -> None:
        stage = _STAGE_BY_PREPARE_STATE.get(self._state)
        if stage is None:
            raise InvalidTransitionError(f"Cannot start stage from {self._state.value}")
        self._generation += 1
        self._invalidate_pending_callbacks()
        self._active_stage = stage
        self._stage_capture_complete = False
        self._stage_capture_success = False
        attempt = self._stage_attempts.get(stage, 0) + 1
        self._active_stage_id = f"{stage.value}-{attempt}"
        try:
            self._metrics_provider.start_stage(session_id=self._session_id, stage_id=self._active_stage_id, stage=stage)
        except Exception as exc:
            self._set_state(CalibrationWizardState.FAILED, cue="stop", message=f"Failed to open stage capture: {exc}")
            return
        self._countdown_seconds = self._prepare_seconds
        self._cue = "prepare"
        self._status_message = "Prepare..."
        token = self._generation
        self._publish()
        self._schedule_live_poll(token)
        self._schedule_prepare_tick(stage, token, self._prepare_seconds)

    def next_step(self) -> None:
        if self._state == CalibrationWizardState.VERIFYING:
            preview_note = "simulated data path" if self._provider_metadata.is_simulated else "live telemetry path"
            self._set_state(
                CalibrationWizardState.PREVIEW,
                cue="prepare",
                message=f"Preview microphone activity, then click Next ({preview_note}).",
            )
            self._schedule_live_poll(self._generation)
            return
        if self._state == CalibrationWizardState.PREVIEW:
            self._enter_prepare_stage(MeasurementStage.SILENCE)
            return
        if self._state in _STAGE_BY_CAPTURE_STATE:
            stage = _STAGE_BY_CAPTURE_STATE[self._state]
            if not (self._stage_capture_complete and self._stage_capture_success):
                raise InvalidTransitionError(f"Cannot proceed; capture for {stage.value} is not successful.")
            if stage == MeasurementStage.SILENCE:
                self._enter_prepare_stage(MeasurementStage.NORMAL)
                return
            if stage == MeasurementStage.NORMAL:
                self._enter_prepare_stage(MeasurementStage.LOUD)
                return
            if stage == MeasurementStage.LOUD:
                if self._phrase_enabled:
                    self._enter_prepare_stage(MeasurementStage.PHRASE)
                else:
                    self._enter_compare()
                return
            if stage == MeasurementStage.PHRASE:
                self._enter_compare()
                return
        if self._state == CalibrationWizardState.COMPARE:
            self._set_state(CalibrationWizardState.COMPLETE, cue="stop", message="Calibration wizard complete.")
            self._end_provider_session(cancelled=False)
            return
        raise InvalidTransitionError(f"Cannot go to next step from {self._state.value}")

    def repeat_stage(self) -> None:
        stage = self._active_measurement_stage()
        if stage is None:
            raise InvalidTransitionError(f"Cannot repeat stage from {self._state.value}")
        self._generation += 1
        self._invalidate_pending_callbacks()
        self._stage_results.pop(stage, None)
        self._latest_metrics = None
        self._enter_prepare_stage(stage)

    def cancel(self) -> None:
        if self._state in {CalibrationWizardState.CANCELLED, CalibrationWizardState.IDLE}:
            return
        self._generation += 1
        self._invalidate_pending_callbacks()
        self._end_provider_session(cancelled=True)
        self._set_state(CalibrationWizardState.CANCELLED, cue="stop", message="Calibration cancelled safely.")

    def close(self) -> None:
        if self._state not in {
            CalibrationWizardState.IDLE,
            CalibrationWizardState.COMPLETE,
            CalibrationWizardState.FAILED,
            CalibrationWizardState.CANCELLED,
        }:
            raise InvalidTransitionError(f"Cannot close wizard from {self._state.value}; cancel first.")
        self._generation += 1
        self._invalidate_pending_callbacks()
        self._end_provider_session(cancelled=True)
        self._active_stage = None
        self._active_stage_id = ""
        self._latest_metrics = None
        self._session_id = ""
        self._countdown_seconds = 0
        self._cue = "idle"
        self._status_message = "Ready to start microphone calibration."
        self._stage_capture_complete = False
        self._stage_capture_success = False
        self._set_state(CalibrationWizardState.IDLE, cue="idle", message=self._status_message)

    def _active_measurement_stage(self) -> MeasurementStage | None:
        if self._state in _STAGE_BY_PREPARE_STATE:
            return _STAGE_BY_PREPARE_STATE[self._state]
        return _STAGE_BY_CAPTURE_STATE.get(self._state)

    def _enter_prepare_stage(self, stage: MeasurementStage) -> None:
        self._invalidate_pending_callbacks()
        self._active_stage = stage
        self._active_stage_id = ""
        self._countdown_seconds = self._prepare_seconds
        self._stage_capture_complete = False
        self._stage_capture_success = False
        self._set_state(
            _PREPARE_STATE_BY_STAGE[stage],
            cue="prepare",
            message=f"{stage.value.title()} stage ready. Click Start Stage to begin countdown.",
        )
        self._schedule_live_poll(self._generation)

    def _enter_compare(self) -> None:
        self._invalidate_pending_callbacks()
        self._active_stage = None
        review_message = (
            "Review simulated stage metrics and continue when ready."
            if self._provider_metadata.is_simulated
            else "Review live telemetry stage metrics and continue when ready."
        )
        self._set_state(CalibrationWizardState.COMPARE, cue="stop", message=review_message)
        self._schedule_live_poll(self._generation)

    def _schedule_prepare_tick(self, stage: MeasurementStage, token: int, remaining: int) -> None:
        if remaining <= 0:
            self._begin_capture(stage, token)
            return

        def _tick() -> None:
            if not self._token_current(token):
                return
            if self._state != _PREPARE_STATE_BY_STAGE[stage]:
                return
            self._countdown_seconds = remaining - 1
            self._cue = "prepare"
            self._status_message = f"Prepare... {max(remaining - 1, 0)}"
            self._publish()
            self._schedule_prepare_tick(stage, token, remaining - 1)

        self._schedule(1000, _tick)

    def _begin_capture(self, stage: MeasurementStage, token: int) -> None:
        if not self._token_current(token):
            return
        self._active_stage = stage
        self._stage_capture_complete = False
        self._stage_capture_success = False
        self._countdown_seconds = self._capture_seconds
        self._set_state(_CAPTURE_STATE_BY_STAGE[stage], cue="start", message=f"START {stage.value} capture now.")
        self._schedule_live_poll(token)
        self._schedule_capture_tick(stage, token, self._capture_seconds)

    def _schedule_capture_tick(self, stage: MeasurementStage, token: int, remaining: int) -> None:
        if remaining <= 0:
            self._finish_capture(stage, token)
            return

        def _tick() -> None:
            if not self._token_current(token):
                return
            if self._state != _CAPTURE_STATE_BY_STAGE[stage]:
                return
            self._countdown_seconds = remaining - 1
            self._cue = "start"
            self._status_message = f"Capturing... {max(remaining - 1, 0)}"
            self._publish()
            self._schedule_capture_tick(stage, token, remaining - 1)

        self._schedule(1000, _tick)

    def _finish_capture(self, stage: MeasurementStage, token: int) -> None:
        if not self._token_current(token):
            return
        attempt = self._stage_attempts.get(stage, 0) + 1
        self._stage_attempts[stage] = attempt
        metrics = self._metrics_provider.finish_stage(
            session_id=self._session_id,
            stage_id=self._active_stage_id,
            stage=stage,
            timeout_seconds=float(self._capture_seconds + 3),
        )
        self._latest_metrics = metrics
        self._countdown_seconds = 0
        self._cue = "stop"
        self._stage_capture_complete = True
        self._stage_capture_success = metrics.capture_success and metrics.telemetry_complete
        if not self._stage_capture_success:
            reason = metrics.failure_reason or f"incomplete telemetry for {stage.value} stage"
            self._set_state(
                CalibrationWizardState.FAILED,
                cue="stop",
                message=f"Capture failed for {stage.value} stage: {reason}",
            )
            return
        self._stage_results[stage] = metrics
        completion_source = "simulated" if self._provider_metadata.is_simulated else "live telemetry"
        self._status_message = f"STOP. {stage.value.title()} capture complete ({completion_source})."
        self._publish()

    def _schedule_live_poll(self, token: int) -> None:
        if not self._session_id:
            return

        def _tick() -> None:
            if not self._token_current(token):
                return
            if self._state in {
                CalibrationWizardState.IDLE,
                CalibrationWizardState.COMPLETE,
                CalibrationWizardState.CANCELLED,
                CalibrationWizardState.FAILED,
            }:
                return
            # Stop polling once a stage capture has finished; the next stage
            # start or state transition will restart polling.
            if self._stage_capture_complete:
                return
            try:
                metrics = self._metrics_provider.poll_live_metrics(session_id=self._session_id)
            except Exception as exc:  # pragma: no cover - telemetry callback boundary
                self._set_state(
                    CalibrationWizardState.FAILED,
                    cue="stop",
                    message=f"Live telemetry polling failed: {exc}",
                )
                return
            if metrics is not None:
                self._latest_metrics = metrics
                self._publish()
            self._schedule_live_poll(token)

        self._schedule(250, _tick)

    def _end_provider_session(self, *, cancelled: bool) -> None:
        if not self._session_id:
            return
        try:
            self._metrics_provider.end_session(session_id=self._session_id, cancelled=cancelled)
        except Exception:
            pass

    def _token_current(self, token: int) -> bool:
        return token == self._generation

    def _schedule(self, delay_ms: int, callback: Callable[[], None]) -> None:
        handle = self._scheduler.call_later(delay_ms, callback)
        self._pending_handles.append(handle)

    def _invalidate_pending_callbacks(self) -> None:
        if not self._pending_handles:
            return
        for handle in self._pending_handles:
            self._scheduler.cancel(handle)
        self._pending_handles.clear()

    def _set_state(self, state: CalibrationWizardState, *, cue: str, message: str) -> None:
        self._state = state
        self._cue = cue
        self._status_message = message
        self._countdown_seconds = (
            0
            if state
            in {
                CalibrationWizardState.COMPARE,
                CalibrationWizardState.COMPLETE,
                CalibrationWizardState.FAILED,
                CalibrationWizardState.CANCELLED,
                CalibrationWizardState.IDLE,
                CalibrationWizardState.VERIFYING,
                CalibrationWizardState.PREVIEW,
            }
            else self._countdown_seconds
        )
        self._publish()

    def _progress(self) -> tuple[int, int]:
        total = 7 if self._phrase_enabled else 6
        mapping = {
            CalibrationWizardState.IDLE: 0,
            CalibrationWizardState.VERIFYING: 1,
            CalibrationWizardState.PREVIEW: 2,
            CalibrationWizardState.PREPARE_SILENCE: 3,
            CalibrationWizardState.CAPTURE_SILENCE: 3,
            CalibrationWizardState.PREPARE_NORMAL: 4,
            CalibrationWizardState.CAPTURE_NORMAL: 4,
            CalibrationWizardState.PREPARE_LOUD: 5,
            CalibrationWizardState.CAPTURE_LOUD: 5,
            CalibrationWizardState.PREPARE_PHRASE: 6,
            CalibrationWizardState.CAPTURE_PHRASE: 6,
            CalibrationWizardState.COMPARE: total,
            CalibrationWizardState.COMPLETE: total,
            CalibrationWizardState.FAILED: min(total, 6),
            CalibrationWizardState.CANCELLED: min(total, 6),
        }
        return mapping[self._state], total

    def _stage_name(self) -> str:
        if self._state in _STAGE_BY_PREPARE_STATE:
            return _STAGE_BY_PREPARE_STATE[self._state].value.title()
        if self._state in _STAGE_BY_CAPTURE_STATE:
            return _STAGE_BY_CAPTURE_STATE[self._state].value.title()
        return self._state.value.replace("_", " ").title()

    def _instruction(self) -> str:
        if self._state == CalibrationWizardState.IDLE:
            return "Launch calibration when ready."
        if self._state == CalibrationWizardState.VERIFYING:
            return "Confirm diagnostics channel and microphone runtime availability."
        if self._state == CalibrationWizardState.PREVIEW:
            return "Speak briefly and watch live metrics to verify microphone responsiveness."
        if self._state in _STAGE_BY_PREPARE_STATE:
            stage = _STAGE_BY_PREPARE_STATE[self._state]
            instructions = {
                MeasurementStage.SILENCE: "Remain silent and keep the environment still.",
                MeasurementStage.NORMAL: "Speak in a normal voice at the standard distance.",
                MeasurementStage.LOUD: "Speak loudly but naturally without shouting into the mic.",
                MeasurementStage.PHRASE: "Read the phrase prompt naturally for transcript validation.",
            }
            return instructions[stage]
        if self._state in _STAGE_BY_CAPTURE_STATE:
            return "Follow the START cue and stop immediately when STOP is shown."
        if self._state == CalibrationWizardState.COMPARE:
            return "Review captured stage metrics and diagnostics before completing this run."
        if self._state == CalibrationWizardState.COMPLETE:
            return "Calibration run complete."
        if self._state == CalibrationWizardState.CANCELLED:
            return "Calibration cancelled and active stage/session invalidated safely."
        if self._state == CalibrationWizardState.FAILED:
            return "Calibration failed due to incomplete/invalid telemetry. Retry the stage or restart."
        return ""

    def _publish(self) -> None:
        current, total = self._progress()
        terminal = self._state in {
            CalibrationWizardState.IDLE,
            CalibrationWizardState.COMPLETE,
            CalibrationWizardState.FAILED,
            CalibrationWizardState.CANCELLED,
        }
        can_start = self._state in _STAGE_BY_PREPARE_STATE or self._state == CalibrationWizardState.IDLE
        can_repeat = self._active_measurement_stage() is not None
        can_next = self._state in {
            CalibrationWizardState.VERIFYING,
            CalibrationWizardState.PREVIEW,
            CalibrationWizardState.COMPARE,
        } or (self._state in _STAGE_BY_CAPTURE_STATE and self._stage_capture_complete and self._stage_capture_success)
        can_cancel = self._state not in {CalibrationWizardState.IDLE, CalibrationWizardState.COMPLETE, CalibrationWizardState.CANCELLED}
        can_close = terminal and self._state != CalibrationWizardState.IDLE
        self._on_update(
            CalibrationWizardViewState(
                state=self._state,
                stage_name=self._stage_name(),
                instruction=self._instruction(),
                cue=self._cue,
                countdown_seconds=self._countdown_seconds,
                progress_current=current,
                progress_total=total,
                can_start=can_start,
                can_repeat=can_repeat,
                can_next=can_next,
                can_cancel=can_cancel,
                can_close=can_close,
                phrase_enabled=self._phrase_enabled,
                status_message=self._status_message,
                stage_results=dict(self._stage_results),
                latest_metrics=self._latest_metrics,
                provider_mode=self._provider_metadata.mode,
                provider_source_label=self._provider_metadata.source_label,
                simulation_mode=self._provider_metadata.is_simulated,
                simulation_warning=self._provider_metadata.simulation_warning,
                telemetry_connection_state=self._metrics_provider.connection_state(),
                session_id=self._session_id,
            )
        )
