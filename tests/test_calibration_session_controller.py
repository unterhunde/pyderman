from __future__ import annotations

import heapq
import unittest
from dataclasses import dataclass
from typing import Callable

from pc.services.calibration_metrics_provider import MeasurementStage, SimulatedCalibrationMetricsProvider
from pc.services.calibration_session_controller import (
    CalibrationSessionController,
    CalibrationWizardState,
    CalibrationWizardViewState,
    InvalidTransitionError,
)


@dataclass
class _ScheduledItem:
    when_ms: int
    handle: int
    callback: Callable[[], None]


class _FakeScheduler:
    def __init__(self) -> None:
        self._now_ms = 0
        self._next_handle = 1
        self._queue: list[tuple[int, int, _ScheduledItem]] = []
        self._cancelled: set[int] = set()

    def call_later(self, delay_ms: int, callback: Callable[[], None]) -> int:
        handle = self._next_handle
        self._next_handle += 1
        item = _ScheduledItem(when_ms=self._now_ms + delay_ms, handle=handle, callback=callback)
        heapq.heappush(self._queue, (item.when_ms, item.handle, item))
        return handle

    def cancel(self, handle: int) -> None:
        self._cancelled.add(handle)

    def advance(self, ms: int) -> None:
        target = self._now_ms + ms
        while self._queue and self._queue[0][0] <= target:
            when_ms, handle, item = heapq.heappop(self._queue)
            self._now_ms = when_ms
            if handle in self._cancelled:
                continue
            item.callback()
        self._now_ms = target

    def run_all(self) -> None:
        while self._queue:
            next_due = self._queue[0][0] - self._now_ms
            self.advance(max(next_due, 0))


class TestCalibrationSessionController(unittest.TestCase):
    _EXPECTED_WARNING = "SIMULATION MODE — Results are test data and are not production microphone calibration values."

    def _make_controller(
        self,
        *,
        phrase_enabled: bool = True,
        failed_attempts: dict[MeasurementStage, set[int]] | None = None,
    ) -> tuple[CalibrationSessionController, _FakeScheduler, list[CalibrationWizardViewState]]:
        updates: list[CalibrationWizardViewState] = []
        scheduler = _FakeScheduler()
        controller = CalibrationSessionController(
            metrics_provider=SimulatedCalibrationMetricsProvider(failed_attempts=failed_attempts),
            scheduler=scheduler,
            on_update=updates.append,
            prepare_seconds=2,
            capture_seconds=2,
            phrase_enabled=phrase_enabled,
        )
        return controller, scheduler, updates

    def _run_stage_capture(self, controller: CalibrationSessionController, scheduler: _FakeScheduler) -> None:
        controller.start_stage()
        scheduler.run_all()

    def _assert_simulation_fields(self, view_state: CalibrationWizardViewState) -> None:
        self.assertTrue(view_state.simulation_mode)
        self.assertEqual(view_state.provider_mode, "simulation")
        self.assertEqual(view_state.provider_source_label, "deterministic-simulated-provider")
        self.assertEqual(view_state.simulation_warning, self._EXPECTED_WARNING)

    def test_valid_state_transition_path_to_complete_with_phrase(self):
        controller, scheduler, updates = self._make_controller(phrase_enabled=True)
        controller.start_wizard()
        controller.next_step()
        controller.next_step()
        self._run_stage_capture(controller, scheduler)  # silence
        controller.next_step()
        self._run_stage_capture(controller, scheduler)  # normal
        controller.next_step()
        self._run_stage_capture(controller, scheduler)  # loud
        controller.next_step()
        self._run_stage_capture(controller, scheduler)  # phrase
        controller.next_step()
        controller.next_step()
        self.assertEqual(updates[-1].state, CalibrationWizardState.COMPLETE)

    def test_invalid_transition_rejected(self):
        controller, _, _ = self._make_controller()
        with self.assertRaises(InvalidTransitionError):
            controller.next_step()
        controller.start_wizard()
        with self.assertRaises(InvalidTransitionError):
            controller.start_stage()

    def test_repeat_stage_restarts_only_current_stage(self):
        controller, scheduler, updates = self._make_controller()
        controller.start_wizard()
        controller.next_step()
        controller.next_step()
        self._run_stage_capture(controller, scheduler)  # silence
        silence_first = updates[-1].stage_results[MeasurementStage.SILENCE].raw_rms
        controller.repeat_stage()
        self.assertEqual(updates[-1].state, CalibrationWizardState.PREPARE_SILENCE)
        self._run_stage_capture(controller, scheduler)
        silence_second = updates[-1].stage_results[MeasurementStage.SILENCE].raw_rms
        self.assertGreater(silence_second, silence_first)
        self.assertNotIn(MeasurementStage.NORMAL, updates[-1].stage_results)

    def test_cancel_during_countdown_suppresses_pending_callbacks(self):
        controller, scheduler, updates = self._make_controller()
        controller.start_wizard()
        controller.next_step()
        controller.next_step()
        controller.start_stage()
        scheduler.advance(500)
        controller.cancel()
        scheduler.run_all()
        self.assertEqual(updates[-1].state, CalibrationWizardState.CANCELLED)

    def test_cancel_during_capture_suppresses_pending_callbacks(self):
        controller, scheduler, updates = self._make_controller()
        controller.start_wizard()
        controller.next_step()
        controller.next_step()
        controller.start_stage()
        scheduler.advance(2200)  # move into capture window
        controller.cancel()
        scheduler.run_all()
        self.assertEqual(updates[-1].state, CalibrationWizardState.CANCELLED)

    def test_stale_callback_suppression_on_repeat(self):
        controller, scheduler, updates = self._make_controller()
        controller.start_wizard()
        controller.next_step()
        controller.next_step()
        controller.start_stage()
        scheduler.advance(1000)
        controller.repeat_stage()
        previous_state = updates[-1].state
        scheduler.run_all()
        self.assertEqual(updates[-1].state, previous_state)
        self.assertEqual(updates[-1].state, CalibrationWizardState.PREPARE_SILENCE)

    def test_optional_phrase_stage_skip(self):
        controller, scheduler, updates = self._make_controller(phrase_enabled=False)
        controller.start_wizard()
        controller.next_step()
        controller.next_step()
        self._run_stage_capture(controller, scheduler)
        controller.next_step()
        self._run_stage_capture(controller, scheduler)
        controller.next_step()
        self._run_stage_capture(controller, scheduler)
        controller.next_step()
        self.assertEqual(updates[-1].state, CalibrationWizardState.COMPARE)

    def test_failure_transition(self):
        controller, scheduler, updates = self._make_controller(
            failed_attempts={MeasurementStage.SILENCE: {1}},
        )
        controller.start_wizard()
        controller.next_step()
        controller.next_step()
        self._run_stage_capture(controller, scheduler)
        self.assertEqual(updates[-1].state, CalibrationWizardState.FAILED)

    def test_view_state_communicates_simulation_mode(self):
        controller, _, updates = self._make_controller()
        controller.start_wizard()
        for update in updates:
            self._assert_simulation_fields(update)

    def test_simulation_warning_persists_through_complete_workflow(self):
        controller, scheduler, updates = self._make_controller(phrase_enabled=True)
        controller.start_wizard()
        controller.next_step()
        controller.next_step()
        self._run_stage_capture(controller, scheduler)
        controller.next_step()
        self._run_stage_capture(controller, scheduler)
        controller.next_step()
        self._run_stage_capture(controller, scheduler)
        controller.next_step()
        self._run_stage_capture(controller, scheduler)
        controller.next_step()
        controller.next_step()
        self.assertEqual(updates[-1].state, CalibrationWizardState.COMPLETE)
        for update in updates:
            self._assert_simulation_fields(update)

    def test_simulation_warning_persists_in_failed_and_cancelled_states(self):
        controller, scheduler, updates = self._make_controller(
            failed_attempts={MeasurementStage.SILENCE: {1}},
        )
        controller.start_wizard()
        controller.next_step()
        controller.next_step()
        self._run_stage_capture(controller, scheduler)
        self.assertEqual(updates[-1].state, CalibrationWizardState.FAILED)
        self._assert_simulation_fields(updates[-1])

        controller.start_wizard()
        controller.next_step()
        controller.next_step()
        controller.start_stage()
        scheduler.advance(500)
        controller.cancel()
        self.assertEqual(updates[-1].state, CalibrationWizardState.CANCELLED)
        self._assert_simulation_fields(updates[-1])


if __name__ == "__main__":
    unittest.main()
