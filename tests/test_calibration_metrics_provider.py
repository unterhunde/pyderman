from __future__ import annotations

import unittest

from pc.services.calibration_metrics_provider import (
    MeasurementStage,
    SimulatedCalibrationMetricsProvider,
    StageMetrics,
)


class TestSimulatedCalibrationMetricsProvider(unittest.TestCase):
    def test_metadata_exposes_simulation_source_designation(self):
        provider = SimulatedCalibrationMetricsProvider()
        metadata = provider.metadata()
        self.assertEqual(metadata.mode, "simulation")
        self.assertTrue(metadata.is_simulated)
        self.assertIn("SIMULATION MODE", metadata.simulation_warning)
        self.assertIn("not production microphone calibration values", metadata.simulation_warning)
        self.assertEqual(metadata.source_label, "deterministic-simulated-provider")

    def test_contract_returns_stage_metrics_fields(self):
        provider = SimulatedCalibrationMetricsProvider()
        metrics = provider.capture(MeasurementStage.NORMAL, attempt=1, capture_seconds=4)
        self.assertIsInstance(metrics, StageMetrics)
        self.assertIsInstance(metrics.raw_rms, float)
        self.assertIsInstance(metrics.processed_rms, float)
        self.assertIsInstance(metrics.peak, float)
        self.assertIsInstance(metrics.clipping, float)
        self.assertIsInstance(metrics.gate_ratio, float)
        self.assertIsInstance(metrics.agc_gain, float)
        self.assertIsInstance(metrics.capture_success, bool)

    def test_deterministic_for_same_input(self):
        provider = SimulatedCalibrationMetricsProvider()
        first = provider.capture(MeasurementStage.LOUD, attempt=2, capture_seconds=4)
        second = provider.capture(MeasurementStage.LOUD, attempt=2, capture_seconds=4)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
