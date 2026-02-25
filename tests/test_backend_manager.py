"""Unit tests for Docker backend lifecycle automation."""

import unittest
from unittest.mock import patch

import backend_manager


class BackendManagerTests(unittest.TestCase):
    @patch("backend_manager._docker_available", return_value=False)
    def test_start_backend_fails_without_docker(self, _mock_available):
        ok, reason = backend_manager.start_backend()
        self.assertFalse(ok)
        self.assertEqual(reason, "docker_missing")

    @patch("backend_manager.time.sleep")
    @patch("backend_manager._docker_daemon_running")
    @patch("backend_manager._docker_available", return_value=True)
    @patch("backend_manager._start_docker_desktop")
    def test_start_backend_fails_when_daemon_never_starts(
        self, _mock_start, _mock_available, mock_daemon, _mock_sleep
    ):
        mock_daemon.return_value = False
        ok, reason = backend_manager.start_backend()
        self.assertFalse(ok)
        self.assertEqual(reason, "docker_not_running")

    @patch("backend_manager._wait_for_kokoro_ready", return_value=(True, "healthy"))
    @patch("backend_manager._start_or_create_container")
    @patch("backend_manager._image_present", return_value=True)
    @patch("backend_manager._docker_daemon_running", return_value=True)
    @patch("backend_manager._docker_available", return_value=True)
    def test_start_backend_starts_container_and_waits(
        self,
        _mock_available,
        _mock_daemon,
        _mock_image,
        mock_start_container,
        mock_wait,
    ):
        mock_start_container.return_value = backend_manager.CommandResult(ok=True, stdout="ok")
        ok, reason = backend_manager.start_backend()
        self.assertTrue(ok)
        self.assertEqual(reason, "healthy")
        mock_wait.assert_called_once()

    @patch("backend_manager.start_backend", return_value=(True, "healthy"))
    @patch("backend_manager.tts_client.check_status", return_value=(False, "connection_refused"))
    def test_ensure_backend_ready_falls_back_to_start(self, _mock_status, mock_start):
        ok, reason = backend_manager.ensure_backend_ready()
        self.assertTrue(ok)
        self.assertEqual(reason, "healthy")
        mock_start.assert_called_once()

    @patch("backend_manager._container_running", return_value=False)
    @patch("backend_manager._docker_daemon_running", return_value=True)
    @patch("backend_manager._docker_available", return_value=True)
    @patch("backend_manager.tts_client.check_status", return_value=(False, "timeout"))
    def test_backend_status_reports_health_reason(
        self, _mock_tts, _mock_available, _mock_daemon, _mock_container
    ):
        status = backend_manager.backend_status()
        self.assertFalse(status["healthy"])
        self.assertEqual(status["reason"], "timeout")
        self.assertTrue(status["docker_available"])
        self.assertTrue(status["docker_running"])
        self.assertFalse(status["container_running"])


if __name__ == "__main__":
    unittest.main()
