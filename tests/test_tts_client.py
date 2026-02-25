"""Unit tests for tts_client module."""

import unittest
from unittest.mock import patch

import requests

import tts_client


class TTSClientTests(unittest.TestCase):
    @patch("tts_client.requests.get")
    def test_check_status_uses_health_urls(self, mock_get):
        mock_get.return_value.status_code = 200
        reachable, reason = tts_client.check_status()

        self.assertTrue(reachable)
        self.assertEqual(reason, "http_200")
        called_urls = [call.args[0] for call in mock_get.call_args_list]
        self.assertIn("http://localhost:8880/web/", called_urls)
        self.assertNotIn("http://localhost:8880/v1/audio/speech", called_urls)

    @patch("tts_client.requests.get")
    def test_check_status_returns_reason_for_failure(self, mock_get):
        mock_get.side_effect = requests.ConnectionError("Connection refused")
        reachable, reason = tts_client.check_status()

        self.assertFalse(reachable)
        self.assertEqual(reason, "connection_refused")

    @patch("tts_client.requests.post")
    def test_synthesize_falls_back_to_next_endpoint(self, mock_post):
        def side_effect(url, **kwargs):
            if "8880" in url:
                raise requests.ConnectionError("down")
            response = unittest.mock.Mock()
            response.status_code = 200
            response.content = b"wav"
            return response

        mock_post.side_effect = side_effect
        output = tts_client.synthesize("hello", "af_heart", 1.0)
        self.assertEqual(output, b"wav")


if __name__ == "__main__":
    unittest.main()
