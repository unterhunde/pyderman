"""Camera and synthetic frame sources."""

from __future__ import annotations

import logging
import time

import cv2
import numpy as np

from pi.video.config import FPS, FRAME_HEIGHT, FRAME_WIDTH

logger = logging.getLogger("pibot.video_streamer")


def open_camera():
    try:
        from picamera2 import Picamera2
    except ImportError:
        logger.warning("Picamera2 unavailable; falling back to synthetic video source")
        return None, "synthetic"

    try:
        picam2 = Picamera2()
        config = picam2.create_video_configuration(
            main={"size": (FRAME_WIDTH, FRAME_HEIGHT), "format": "RGB888"},
            controls={"FrameRate": FPS},
        )
        picam2.configure(config)
        picam2.start()
        logger.info("Camera opened successfully (%sx%s @ %s FPS)", FRAME_WIDTH, FRAME_HEIGHT, FPS)
        return picam2, "picamera2"
    except Exception:
        logger.exception("Camera initialization failed; using synthetic source")
        return None, "synthetic"


def synthetic_frame(frame_id: int) -> np.ndarray:
    frame = np.zeros((FRAME_HEIGHT, FRAME_WIDTH, 3), dtype=np.uint8)
    color = int((frame_id * 7) % 255)
    frame[:, :] = (30, 30, 30 + color // 8)
    cv2.putText(
        frame,
        f"SYNTHETIC FRAME {frame_id}",
        (32, 60),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (0, 255, 255),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        frame,
        time.strftime("%H:%M:%S"),
        (32, 110),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    return frame

