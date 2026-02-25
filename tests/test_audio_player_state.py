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

    def test_estimate_word_end_times_monotonic_and_ends_at_duration(self):
        end_times = self.player._estimate_word_end_times(["hello", "world"], 1.0)
        self.assertEqual(len(end_times), 2)
        self.assertGreaterEqual(end_times[0], 0.0)
        self.assertGreater(end_times[1], end_times[0])
        self.assertAlmostEqual(end_times[-1], 1.0)

    def test_word_index_for_time_handles_boundaries(self):
        end_times = [0.2, 0.5, 1.0]
        self.assertEqual(self.player._word_index_for_time(0.0, end_times), 0)
        self.assertEqual(self.player._word_index_for_time(0.3, end_times), 1)
        self.assertEqual(self.player._word_index_for_time(1.2, end_times), 2)
        self.assertEqual(self.player._word_index_for_time(0.1, []), -1)

    def test_on_word_change_callback_receives_payload(self):
        cb = MagicMock()
        self.player.on_word_change(cb)
        self.player._notify_word_change(0, 2, 1, ["hi", "there"], "hi there")
        cb.assert_called_once_with(0, 2, 1, ["hi", "there"], "hi there")


if __name__ == "__main__":
    unittest.main()
