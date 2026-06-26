"""YoloPacket: structured container for YOLO detection results.

Packages the data from a single YOLO Results object into a clean, serialisable
dataclass ready to be passed into a rule + context pipeline for an Ollama AI.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional
import numpy as np


@dataclass
class YoloObject:
    """A single detected object within a frame."""

    label: str
    confidence: float
    # Bounding box in [x1, y1, x2, y2] pixel coordinates.
    bbox: tuple[float, float, float, float]
    # Tracker-assigned ID; None when tracking is not active.
    track_id: Optional[int] = None

    @property
    def center(self) -> tuple[float, float]:
        """Centre pixel of the bounding box."""
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2, (y1 + y2) / 2)

    @property
    def area(self) -> float:
        """Pixel area of the bounding box."""
        x1, y1, x2, y2 = self.bbox
        return (x2 - x1) * (y2 - y1)


@dataclass
class YoloPacket:
    """Packages YOLO tracking results for downstream Ollama AI processing.

    Build from a single Ultralytics Results object::

        packet = YoloPacket.from_results(results[0], frame_id=42)

    The packet is then forwarded to the rule + context pipeline.
    """

    # Monotonically increasing identifier matching the video frame.
    frame_id: int
    # Wall-clock timestamp (seconds since epoch) when the packet was created.
    timestamp: float
    # Original frame dimensions (height, width).
    frame_shape: tuple[int, int]
    # All detections in this frame, sorted by confidence descending.
    detections: list[YoloObject] = field(default_factory=list)
    # Free-form context string that rules may populate before AI inference.
    context: str = ""

    # ------------------------------------------------------------------ #
    # Convenience constructors                                             #
    # ------------------------------------------------------------------ #

    @classmethod
    def from_results(cls, result, frame_id: int) -> "YoloPacket":
        """Build a YoloPacket from a single Ultralytics Results object.

        Args:
            result:   The first (or only) element of the list returned by
                      ``model.track(frame, ...)``.
            frame_id: The application-level frame counter for this frame.
        """
        orig_shape = result.orig_shape  # (height, width)
        names = result.names           # {class_id: label_str}

        detections: list[YoloObject] = []

        boxes = result.boxes
        if boxes is not None and len(boxes):    
            xyxy = boxes.xyxy.cpu().numpy()          # (N, 4)
            confs = boxes.conf.cpu().numpy()         # (N,)
            cls_ids = boxes.cls.cpu().numpy().astype(int)  # (N,)
            track_ids = (
                boxes.id.cpu().numpy().astype(int)
                if boxes.id is not None
                else [None] * len(xyxy)
            )

            for bbox, conf, cls_id, tid in zip(xyxy, confs, cls_ids, track_ids):
                detections.append(
                    YoloObject(
                        label=names[cls_id],
                        confidence=float(conf),
                        bbox=(float(bbox[0]), float(bbox[1]),
                              float(bbox[2]), float(bbox[3])),
                        track_id=int(tid) if tid is not None else None,
                    )
                )

        detections.sort(key=lambda d: d.confidence, reverse=True)

        return cls(
            frame_id=frame_id,
            timestamp=time.time(),
            frame_shape=(int(orig_shape[0]), int(orig_shape[1])),
            detections=detections,
        )

    # ------------------------------------------------------------------ #
    # Helpers for the AI pipeline                                          #
    # ------------------------------------------------------------------ #

    @property
    def labels(self) -> list[str]:
        """Unique object labels present in the frame."""
        seen: set[str] = set()
        return [d.label for d in self.detections if not (d.label in seen or seen.add(d.label))]  # type: ignore[func-returns-value]

    @property
    def detection_count(self) -> int:
        return len(self.detections)

    def to_prompt_context(self) -> str:
        """Render a compact human-readable summary for injection into an LLM prompt."""
        lines = [
            f"Frame {self.frame_id} | {self.detection_count} detection(s) | "
            f"{self.frame_shape[1]}x{self.frame_shape[0]}px"
        ]
        for d in self.detections:
            tid = f" [track {d.track_id}]" if d.track_id is not None else ""
            lines.append(
                f"  - {d.label}{tid}: conf={d.confidence:.2f} "
                f"bbox=({d.bbox[0]:.0f},{d.bbox[1]:.0f},"
                f"{d.bbox[2]:.0f},{d.bbox[3]:.0f}) "
                f"center=({d.center[0]:.0f},{d.center[1]:.0f})"
            )
        if self.context:
            lines.append(f"Context: {self.context}")
        return "\n".join(lines)
