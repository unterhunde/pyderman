"""Thread health monitoring and automatic recovery."""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable


class ThreadMonitor:
    """Monitor worker threads and restart on failure."""
    
    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        self._monitored_threads: dict[str, dict] = {}
        self._monitor_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
    
    def register_thread(
        self,
        name: str,
        thread_obj: threading.Thread,
        restart_callback: Callable[[], threading.Thread] | None = None,
        on_death: Callable[[], None] | None = None,
    ) -> None:
        """Register a worker thread to monitor.
        
        Args:
            name: Thread name for logging
            thread_obj: Thread object to monitor
            restart_callback: Function to call to restart thread if it dies
            on_death: Callback when thread dies (before restart attempt)
        """
        with self._lock:
            self._monitored_threads[name] = {
                "thread": thread_obj,
                "restart_callback": restart_callback,
                "on_death": on_death,
                "last_check": time.monotonic(),
                "alive_count": 0,
            }
    
    def start(self) -> None:
        """Start the monitor thread."""
        if self._monitor_thread is not None and self._monitor_thread.is_alive():
            return
        self._stop_event.clear()
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        self.logger.info("Thread monitor started")
    
    def stop(self) -> None:
        """Stop the monitor thread."""
        self._stop_event.set()
        if self._monitor_thread is not None:
            self._monitor_thread.join(timeout=2.0)
        self.logger.info("Thread monitor stopped")
    
    def _monitor_loop(self) -> None:
        """Main monitor loop - checks thread health periodically."""
        check_interval = 1.0
        while not self._stop_event.is_set():
            with self._lock:
                threads_to_check = dict(self._monitored_threads)
            
            for name, thread_info in threads_to_check.items():
                self._check_thread(name, thread_info)
            
            time.sleep(check_interval)
    
    def _check_thread(self, name: str, thread_info: dict) -> None:
        """Check if thread is still alive and restart if needed."""
        thread_obj = thread_info.get("thread")
        if thread_obj is None:
            return
        
        is_alive = thread_obj.is_alive()
        
        if is_alive:
            with self._lock:
                thread_info["alive_count"] += 1
        else:
            # Thread died
            self.logger.error("Worker thread died: %s", name)
            
            # Call death callback if provided
            if thread_info.get("on_death") is not None:
                try:
                    thread_info["on_death"]()
                except Exception:
                    self.logger.exception("Error in on_death callback for %s", name)
            
            # Try to restart if callback provided
            if thread_info.get("restart_callback") is not None:
                try:
                    self.logger.info("Attempting to restart thread: %s", name)
                    new_thread = thread_info["restart_callback"]()
                    with self._lock:
                        if name in self._monitored_threads:
                            self._monitored_threads[name]["thread"] = new_thread
                            self._monitored_threads[name]["alive_count"] = 0
                    self.logger.info("Thread restarted successfully: %s", name)
                except Exception:
                    self.logger.exception("Failed to restart thread: %s", name)
    
    def get_status(self) -> dict[str, str]:
        """Get status of all monitored threads."""
        status = {}
        with self._lock:
            for name, thread_info in self._monitored_threads.items():
                thread_obj = thread_info.get("thread")
                is_alive = thread_obj.is_alive() if thread_obj else False
                status[name] = "running" if is_alive else "dead"
        return status
