"""Unit tests for text utility helpers."""

import unittest
from unittest.mock import patch

import text_utils


class TextUtilsTests(unittest.TestCase):
    def test_split_sentences_handles_newlines_and_punctuation(self):
        text = "Hello world.\n\nHow are you? Great!"
        result = text_utils.split_sentences(text)
        self.assertEqual(result, ["Hello world.", "How are you?", "Great!"])

    @patch("text_utils._write_clipboard")
    @patch("text_utils._clipboard_change_count")
    @patch("text_utils._simulate_cmd_c")
    @patch("text_utils._read_clipboard")
    def test_get_selected_text_ignores_whitespace(
        self, mock_read, _mock_copy, mock_count, _mock_write
    ):
        mock_read.side_effect = ["prior", "   ", "   "]
        mock_count.side_effect = [1, 2, 2, 2]
        value = text_utils.get_selected_text(copy_delay_s=0.02)
        self.assertIsNone(value)

    @patch("text_utils._write_clipboard")
    @patch("text_utils._clipboard_change_count")
    @patch("text_utils._simulate_cmd_c")
    @patch("text_utils._read_clipboard")
    def test_get_selected_text_returns_none_when_not_changed(
        self, mock_read, _mock_copy, mock_count, _mock_write
    ):
        mock_read.side_effect = ["same text", "same text"]
        mock_count.side_effect = [5, 5, 5, 5, 5]
        value = text_utils.get_selected_text(copy_delay_s=0.02)
        self.assertIsNone(value)

    @patch("text_utils._write_clipboard")
    @patch("text_utils._clipboard_change_count")
    @patch("text_utils._simulate_cmd_c")
    @patch("text_utils._read_clipboard")
    def test_get_selected_text_returns_trimmed_text(
        self, mock_read, _mock_copy, mock_count, _mock_write
    ):
        mock_read.side_effect = ["old", "  new text  "]
        mock_count.side_effect = [1, 2, 2, 2]
        value = text_utils.get_selected_text(copy_delay_s=0.02)
        self.assertEqual(value, "new text")


if __name__ == "__main__":
    unittest.main()
