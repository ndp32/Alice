"""State transition tests for AudioPlayer."""

import unittest
from unittest.mock import MagicMock, patch

from audio_player import AudioPlayer


class FakeTTS:
    def __init__(self):
        self.calls = []

    def synthesize(self, text, voice, speed):
        self.calls.append((text, voice, speed))
        return b"wav"


class AudioPlayerStateTests(unittest.TestCase):
    def setUp(self):
        self.tts = FakeTTS()
        self.player = AudioPlayer(self.tts, "af_heart", 1.0)
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
            self.player._prefetch_worker(1, current_gen, "af_heart", 1.0)
            mock_get_audio.assert_not_called()

    @patch.object(AudioPlayer, "_play_sentence")
    @patch.object(AudioPlayer, "_stop_stream")
    def test_seek_sentence_while_paused_updates_index_without_playing(
        self, mock_stop_stream, mock_play
    ):
        self.player.seek_sentence(1)
        self.assertEqual(self.player.current_index, 1)
        mock_stop_stream.assert_called_once()
        mock_play.assert_not_called()

    @patch.object(AudioPlayer, "_play_sentence")
    @patch.object(AudioPlayer, "_stop_stream")
    def test_seek_sentence_while_playing_restarts_from_target_index(
        self, mock_stop_stream, mock_play
    ):
        self.player._playing = True
        self.player.seek_sentence(1)
        self.assertEqual(self.player.current_index, 1)
        mock_stop_stream.assert_called_once()
        mock_play.assert_called_once()
        called_idx = mock_play.call_args.args[0]
        self.assertEqual(called_idx, 1)

    @patch.object(AudioPlayer, "_play_sentence")
    @patch.object(AudioPlayer, "_stop_stream")
    def test_seek_sentence_clamps_out_of_range_indices(self, _mock_stop_stream, _mock_play):
        self.player.seek_sentence(99)
        self.assertEqual(self.player.current_index, 1)
        self.player.seek_sentence(-100)
        self.assertEqual(self.player.current_index, 0)

    def test_get_audio_cache_key_isolated_by_voice_and_speed(self):
        self.player._sentences = ["hello"]
        with patch.object(self.player, "_decode_wav", return_value="pcm"):
            self.assertEqual(self.player._get_audio(0, "af_heart", 1.0), "pcm")
            self.assertEqual(self.player._get_audio(0, "af_heart", 1.0), "pcm")
            self.assertEqual(self.player._get_audio(0, "bf_alice", 1.0), "pcm")
            self.assertEqual(self.player._get_audio(0, "bf_alice", 1.2), "pcm")

        self.assertEqual(len(self.tts.calls), 3)
        self.assertEqual(self.tts.calls[0], ("hello", "af_heart", 1.0))
        self.assertEqual(self.tts.calls[1], ("hello", "bf_alice", 1.0))
        self.assertEqual(self.tts.calls[2], ("hello", "bf_alice", 1.2))

    def test_setters_update_tuning_for_future_requests(self):
        self.player._sentences = ["first"]
        self.player.set_voice("bf_alice")
        self.player.set_speed(1.2)
        with patch.object(self.player, "_decode_wav", return_value="pcm"):
            self.player._get_audio(0, self.player._voice, self.player._speed)

        self.assertEqual(self.tts.calls[-1], ("first", "bf_alice", 1.2))


if __name__ == "__main__":
    unittest.main()
