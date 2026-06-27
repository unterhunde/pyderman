from __future__ import annotations

import unittest

from pc.gui.calibration_wizard_panel import _format_stage_result_line
from pc.services.calibration_metrics_provider import StageMetrics


class TestCalibrationWizardPanelFormatting(unittest.TestCase):
    def test_results_line_marks_simulated_metrics(self):
        metrics = StageMetrics(
            raw_rms=0.1,
            processed_rms=0.09,
            peak=0.2,
            clipping=0.0,
            gate_ratio=0.5,
            agc_gain=1.2,
            capture_success=True,
        )
        line = _format_stage_result_line("Normal", metrics, simulated=True)
        self.assertIn("Normal (SIMULATED):", line)

    def test_results_line_without_simulation_marker_for_non_simulated_mode(self):
        metrics = StageMetrics(
            raw_rms=0.1,
            processed_rms=0.09,
            peak=0.2,
            clipping=0.0,
            gate_ratio=0.5,
            agc_gain=1.2,
            capture_success=True,
        )
        line = _format_stage_result_line("Normal", metrics, simulated=False)
        self.assertTrue(line.startswith("Normal:"))
        self.assertNotIn("SIMULATED", line)


if __name__ == "__main__":
    unittest.main()
