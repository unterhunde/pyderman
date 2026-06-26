"""Frame decode + YOLO inference processing."""

from __future__ import annotations

import cv2
import numpy as np
from ultralytics import YOLO


class InferenceEngine:
    def __init__(self, model_path: str) -> None:
        self.model_path = model_path
        self._model: YOLO | None = None

    def load_model(self) -> YOLO:
        if self._model is None:
            self._model = YOLO(self.model_path)
        return self._model

    def process(self, jpeg_bytes: bytes, inference_enabled: bool) -> tuple[np.ndarray | None, int, float]:
        jpeg_array = np.frombuffer(jpeg_bytes, dtype=np.uint8)
        frame = cv2.imdecode(jpeg_array, cv2.IMREAD_COLOR)
        if frame is None:
            return None, 0, 0.0

        inference_ms = 0.0
        detection_count = 0
        if inference_enabled:
            import time

            started = time.perf_counter()
            results = self.load_model().track(frame, verbose=False)
            frame = results[0].plot()
            boxes = results[0].boxes
            detection_count = int(len(boxes)) if boxes is not None else 0
            inference_ms = (time.perf_counter() - started) * 1000.0

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return frame_rgb, detection_count, inference_ms

