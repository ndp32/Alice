"""State transition tests for AudioPlayer."""

import unittest
from unittest.mock import MagicMock, patch

from audio_player import AudioPlayer


class FakeTTS:
    def synthesize(self, text, voice, speed):
        return None


class AudioPlayerStateTests(unittest.TestCase):
    def setUp(self):
        self.player = AudioPlayer(FakeTTS(), "af_heart", 1.0)
        self.player.load_sentences(["a", "b"])

    @patch.object(AudioPlayer, "_play_sentence")
    def test_prev_sentence_at_start_restarts_index_zero(self, mock_play):
        self.player.prev_sentence()
        self.assertEqual(self.player.current_index, 0)
        self.assertTrue(mock_play.called)

    @patch.object(AudioPlayer, "_stop_stream")
    def test_next_sentence_at_end_finishes_playback(self, mock_stop_stream):
        self.player.load_sentences(["only"])
        done_cb = MagicMock()
        self.player.on_playback_done(done_cb)

        self.player.next_sentence()

        mock_stop_stream.assert_called()
        done_cb.assert_called_once()
        self.assertFalse(self.player.is_playing)

    def test_prefetch_worker_ignores_stale_generation(self):
        current_gen = self.player._generation
        self.player._generation += 1
        with patch.object(self.player, "_get_audio") as mock_get_audio:
            self.player._prefetch_worker(1, current_gen)
            mock_get_audio.assert_not_called()


if __name__ == "__main__":
    unittest.main()
