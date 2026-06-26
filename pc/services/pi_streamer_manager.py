"""Manage Pi-side streamer processes over SSH."""

from __future__ import annotations

import shlex
import subprocess
import threading
import time


class PiStreamerManager:
    def __init__(self, settings) -> None:
        self.settings = settings
        # Lock to prevent concurrent SSH operations from overwhelming Pi
        self._ssh_lock = threading.Lock()
        self._last_ssh_time = 0
        self._ssh_min_interval = 0.1  # Minimum 100ms between SSH commands

    def query_status(self, streamer: str) -> tuple[bool, str]:
        pid_file = f"{self.settings.pi_project_path}/.run/{streamer}_streamer.pid"
        
        # Simple check: if PID file exists and process is alive, it's running
        remote_cmd = (
            f"if [ -f {pid_file} ]; then "
            f"pid=$(cat {pid_file}); kill -0 $pid 2>/dev/null && echo running || echo stopped; "
            f"else echo stopped; "
            f"fi"
        )
        result = self._run_ssh(remote_cmd, timeout=12)
        if result is None:
            return False, "error: ssh-failed"

        code, output = result
        if code != 0:
            return False, output or "unknown-error"
        if output == "running":
            return True, "running"
        return False, "stopped"

    def run_action(self, streamer: str, action: str) -> tuple[bool, str]:
        """Execute a start or stop action on a streamer process."""
        target_script = "pi/mic_udp_streamer.py" if streamer == "mic" else "pi/video_udp_streamer.py"
        pid_file = f"{self.settings.pi_project_path}/.run/{streamer}_streamer.pid"
        log_file = f"{self.settings.pi_project_path}/.run/{streamer}_streamer.log"

        if action == "start":
            # Simple start: launch the streamer and save PID
            remote_cmd = (
                f"cd {self.settings.pi_project_path} && "
                f"nohup {self.settings.pi_venv_path}/bin/python {target_script} "
                f"> {log_file} 2>&1 & "
                f"echo $! > {pid_file}; sleep 0.5; "
                f"kill -0 $(cat {pid_file}) 2>/dev/null && echo started || echo failed"
            )
        else:
            # Simple stop: kill the process and clean up PID file
            remote_cmd = (
                f"if [ -f {pid_file} ]; then "
                f"pid=$(cat {pid_file}); kill $pid 2>/dev/null; rm -f {pid_file}; echo stopped; "
                f"else echo already-stopped; "
                f"fi"
            )

        result = self._run_ssh(remote_cmd, timeout=20)
        if result is None:
            return False, "ssh-failed"
        code, output = result
        if code == 0:
            return True, output or f"{action}ed"
        return False, output or "failed"

    def _run_ssh(self, remote_cmd: str, timeout: int) -> tuple[int, str] | None:
        """Execute SSH command with rate limiting to avoid overwhelming Pi.
        
        Rate limits concurrent SSH operations to prevent SSH connection exhaustion
        on the Raspberry Pi.
        """
        with self._ssh_lock:
            # Rate limit: ensure minimum interval between SSH commands
            elapsed = time.time() - self._last_ssh_time
            if elapsed < self._ssh_min_interval:
                time.sleep(self._ssh_min_interval - elapsed)
            
            ssh_target = f"{self.settings.pi_user}@{self.settings.pi_host}"
            # SSH executes the command through the remote shell by default
            # No need to explicitly invoke bash -lc; just pass the command directly
            cmd = ["ssh", "-o", "ConnectTimeout=8", ssh_target, remote_cmd]
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
            except subprocess.TimeoutExpired:
                return None
            except Exception:
                return None
            finally:
                self._last_ssh_time = time.time()

        output = (result.stdout or "").strip() or (result.stderr or "").strip()
        return result.returncode, output

