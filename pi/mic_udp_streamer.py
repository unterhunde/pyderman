#!/usr/bin/env python3
"""Pi audio streamer composition root."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from pibot_config import load_settings
from pi.audio.streamer import UDPMicStreamer


def main() -> None:
    import os
    import atexit
    from pathlib import Path
    
    settings = load_settings()
    
    # Write PID file for management
    pid_file = Path(settings.pi_project_path) / ".run" / "mic_streamer.pid"
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(os.getpid()))
    
    # Ensure PID file is cleaned up on exit (graceful shutdown or crash)
    def cleanup_pid():
        try:
            pid_file.unlink()
        except Exception:
            pass
    atexit.register(cleanup_pid)
    
    streamer = UDPMicStreamer(
        host=settings.pc_host,
        port=settings.udp_audio_port,
        sample_rate=settings.pi_sample_rate,
        calibration_bind_host=settings.pi_calibration_bind_host,
        calibration_port=settings.calibration_diagnostics_port,
    )
    streamer.run()


if __name__ == "__main__":
    main()
