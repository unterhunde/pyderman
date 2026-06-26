"""Tests for PiStreamerManager reliability fixes.

Covers:
- Stale PID file (dead process) reports stopped, not running
- PID reuse (unrelated process) does not report running
- Stop does not return success when process remains alive after SIGKILL
- Start does not report success if the process exits during the health-check window
"""

from __future__ import annotations

import unittest
from unittest.mock import patch, MagicMock


class _Settings:
    pi_project_path = "/home/jorg/pibot"
    pi_venv_path = "/home/jorg/venv"
    pi_user = "jorg"
    pi_host = "192.168.0.38"


def _make_manager():
    from pc.services.pi_streamer_manager import PiStreamerManager
    return PiStreamerManager(_Settings())


class TestQueryStatus(unittest.TestCase):
    """query_status() correctness including stale/reused PID guards."""

    def _patch_ssh(self, return_value):
        return patch.object(
            __import__("pc.services.pi_streamer_manager", fromlist=["PiStreamerManager"]).PiStreamerManager,
            "_run_ssh",
            return_value=return_value,
        )

    def test_no_pid_file_reports_stopped(self):
        """When the Pi reports stopped (no PID file), result is (False, 'stopped')."""
        manager = _make_manager()
        with patch.object(manager, "_run_ssh", return_value=(0, "stopped")):
            ok, status = manager.query_status("video")
        self.assertFalse(ok)
        self.assertEqual(status, "stopped")

    def test_stale_pid_file_dead_process_reports_stopped(self):
        """Stale PID file whose process is dead: remote script echoes 'stopped'."""
        manager = _make_manager()
        # kill -0 $pid fails (dead) → remote script echoes stopped
        with patch.object(manager, "_run_ssh", return_value=(0, "stopped")):
            ok, status = manager.query_status("video")
        self.assertFalse(ok)
        self.assertEqual(status, "stopped")

    def test_pid_reuse_unrelated_process_reports_stopped(self):
        """PID alive but cmdline does not contain the streamer name → stopped."""
        manager = _make_manager()
        # kill -0 succeeds but grep on cmdline fails → remote script echoes stopped
        with patch.object(manager, "_run_ssh", return_value=(0, "stopped")):
            ok, status = manager.query_status("video")
        self.assertFalse(ok)
        self.assertEqual(status, "stopped")

    def test_live_streamer_reports_running(self):
        """Live streamer with matching cmdline reports running."""
        manager = _make_manager()
        with patch.object(manager, "_run_ssh", return_value=(0, "running")):
            ok, status = manager.query_status("video")
        self.assertTrue(ok)
        self.assertEqual(status, "running")

    def test_ssh_failure_reports_error(self):
        """SSH failure (None) returns (False, 'error: ssh-failed')."""
        manager = _make_manager()
        with patch.object(manager, "_run_ssh", return_value=None):
            ok, status = manager.query_status("mic")
        self.assertFalse(ok)
        self.assertIn("ssh-failed", status)

    def test_query_status_command_contains_cmdline_guard(self):
        """Verify the SSH command includes a /proc/$pid/cmdline check."""
        manager = _make_manager()
        captured = []

        def capture(cmd, timeout):
            captured.append(cmd)
            return (0, "stopped")

        with patch.object(manager, "_run_ssh", side_effect=capture):
            manager.query_status("video")

        self.assertTrue(captured, "Expected _run_ssh to be called")
        self.assertIn("cmdline", captured[0],
                      "query_status command must check /proc/$pid/cmdline to guard against PID reuse")
        self.assertIn("video_udp_streamer", captured[0],
                      "query_status command must verify the streamer script name in cmdline")


class TestRunActionStop(unittest.TestCase):
    """run_action(streamer, 'stop') correctness."""

    def test_stop_success_when_process_dies(self):
        """Stop returns (True, 'stopped') when the process dies normally."""
        manager = _make_manager()
        with patch.object(manager, "_run_ssh", return_value=(0, "stopped")):
            ok, status = manager.run_action("video", "stop")
        self.assertTrue(ok)
        self.assertEqual(status, "stopped")

    def test_stop_already_stopped(self):
        """Stop returns success for 'already-stopped' (no PID file present)."""
        manager = _make_manager()
        with patch.object(manager, "_run_ssh", return_value=(0, "already-stopped")):
            ok, status = manager.run_action("video", "stop")
        self.assertTrue(ok)
        self.assertEqual(status, "already-stopped")

    def test_stop_does_not_succeed_when_process_survives(self):
        """Stop returns (False, 'stop-failed') when process survives SIGKILL."""
        manager = _make_manager()
        # Remote script echoes stop-failed when kill -0 still succeeds after SIGKILL
        with patch.object(manager, "_run_ssh", return_value=(0, "stop-failed")):
            ok, status = manager.run_action("video", "stop")
        self.assertFalse(ok,
            "run_action must not report success when process survives SIGKILL")
        self.assertEqual(status, "stop-failed")

    def test_stop_command_uses_sigterm_before_sigkill(self):
        """Verify stop command sends plain kill (SIGTERM) before kill -9 (SIGKILL)."""
        manager = _make_manager()
        captured = []

        def capture(cmd, timeout):
            captured.append(cmd)
            return (0, "stopped")

        with patch.object(manager, "_run_ssh", side_effect=capture):
            manager.run_action("video", "stop")

        self.assertTrue(captured)
        cmd = captured[0]
        # Plain 'kill $pid' must appear before 'kill -9 $pid'
        term_pos = cmd.find("kill $pid")
        kill9_pos = cmd.find("kill -9")
        self.assertGreater(term_pos, -1,
            "stop command must send SIGTERM (kill $pid) first")
        self.assertGreater(kill9_pos, -1,
            "stop command must escalate to SIGKILL (kill -9)")
        self.assertLess(term_pos, kill9_pos,
            "SIGTERM must be sent before SIGKILL")

    def test_stop_command_removes_pid_file_only_after_confirmed_dead(self):
        """Verify rm -f of the PID file happens after the liveness check, not before."""
        manager = _make_manager()
        captured = []

        def capture(cmd, timeout):
            captured.append(cmd)
            return (0, "stopped")

        with patch.object(manager, "_run_ssh", side_effect=capture):
            manager.run_action("video", "stop")

        cmd = captured[0]
        kill9_pos = cmd.find("kill -9")
        rm_pos = cmd.find("rm -f")
        self.assertGreater(kill9_pos, -1, "stop command must include SIGKILL")
        self.assertGreater(rm_pos, -1, "stop command must include rm -f of PID file")
        self.assertLess(kill9_pos, rm_pos,
            "rm -f must occur after SIGKILL (i.e. after death is confirmed)")


class TestRunActionStart(unittest.TestCase):
    """run_action(streamer, 'start') correctness."""

    def test_start_success(self):
        """Start returns (True, 'started') when process is alive after health check."""
        manager = _make_manager()
        with patch.object(manager, "_run_ssh", return_value=(0, "started")):
            ok, status = manager.run_action("video", "start")
        self.assertTrue(ok)
        self.assertEqual(status, "started")

    def test_start_fails_if_process_exits_during_health_window(self):
        """Start returns (False, 'failed') when process dies before health check completes."""
        manager = _make_manager()
        # Remote polling loop detects the process has died → echoes failed
        with patch.object(manager, "_run_ssh", return_value=(0, "failed")):
            ok, status = manager.run_action("mic", "start")
        self.assertFalse(ok,
            "run_action must not report success if process exits during the health window")
        self.assertEqual(status, "failed")

    def test_start_command_uses_polling_loop_not_single_sleep(self):
        """Verify start command uses a polling loop, not a fixed single sleep."""
        manager = _make_manager()
        captured = []

        def capture(cmd, timeout):
            captured.append(cmd)
            return (0, "started")

        with patch.object(manager, "_run_ssh", side_effect=capture):
            manager.run_action("video", "start")

        self.assertTrue(captured)
        cmd = captured[0]
        # Must use a loop construct
        self.assertIn("for i in", cmd,
            "start command must use a polling loop for the health check")
        # The loop must be properly closed with 'done'
        self.assertIn("done;", cmd,
            "start command loop must be closed with 'done'")
        # Must break out of the loop when process dies (|| break)
        self.assertIn("|| break", cmd,
            "start command loop must break early when process dies")

    def test_start_command_health_check_polls_at_least_2_seconds(self):
        """Verify the polling loop covers at least 2 s total (4 × 0.5 s)."""
        manager = _make_manager()
        captured = []

        def capture(cmd, timeout):
            captured.append(cmd)
            return (0, "started")

        with patch.object(manager, "_run_ssh", side_effect=capture):
            manager.run_action("mic", "start")

        cmd = captured[0]
        # seq 1 4 with 0.5 s sleep = 2 s
        self.assertIn("seq 1 4", cmd,
            "start polling loop must run 4 iterations for a 2 s window")
        self.assertIn("sleep 0.5", cmd,
            "start polling loop must use 0.5 s sleep intervals")


if __name__ == "__main__":
    unittest.main()
