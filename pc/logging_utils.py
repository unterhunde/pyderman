"""Logging helpers for the operator console."""

from __future__ import annotations

import logging
import queue


class GuiLogHandler(logging.Handler):
    def __init__(self, target_queue: queue.Queue[str]) -> None:
        super().__init__()
        self.target_queue = target_queue

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.target_queue.put_nowait(self.format(record))
        except queue.Full:
            pass

