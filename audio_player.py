"""Audio playback engine with sentence queue, pre-fetching, and navigation."""

import io
import re
import threading
import wave

import numpy as np
import sounddevice as sd

from config import PREFETCH_ENABLED


class AudioPlayer:
    def __init__(self, tts_client, voice: str, speed: float):
        self._tts = tts_client
        self._voice = voice
        self._speed = speed

        self._sentences: list[str] = []
        self._current_idx = 0
        self._audio_cache: dict[tuple[int, str, float], np.ndarray] = {}
        self._sample_rate = 24000

        self._stream: sd.OutputStream | None = None
        self._play_pos = 0  # current position in the sample buffer
        self._current_samples: np.ndarray | None = None

        self._playing = False
        self._stopped = False  # True after stop() — no more playback
        self._lock = threading.Lock()
        self._generation = 0

        self._on_sentence_change_cb = None
        self._on_word_change_cb = None
        self._on_playback_done_cb = None

        self._prefetch_thread: threading.Thread | None = None
        self._word_tokens: list[str] = []
        self._word_end_times_s: list[float] = []
        self._last_word_idx = -1

    # -- Public API --

    def load_sentences(self, sentences: list[str]) -> None:
        with self._lock:
            self._sentences = sentences
            self._current_idx = 0
            self._audio_cache.clear()
            self._stopped = False
            self._generation += 1

    def play(self) -> None:
        """Start or resume playback from current sentence."""
        with self._lock:
            if self._stopped or not self._sentences:
                return
            self._playing = True
            idx = self._current_idx
            generation = self._generation

        # If we have a paused stream with remaining samples, resume it
        if self._stream is not None and self._current_samples is not None:
            self._stream.start()
            return

        # Otherwise, start playing the current sentence
        self._play_sentence(idx, generation)

    def pause(self) -> None:
        with self._lock:
            self._playing = False
        if self._stream is not None:
            self._stream.stop()

    def toggle_play_pause(self) -> None:
        if self._playing:
            self.pause()
        else:
            self.play()

    def next_sentence(self) -> None:
        with self._lock:
            if self._current_idx >= len(self._sentences) - 1:
                # At last sentence — stop playback
                self._playing = False
                self._generation += 1
                self._stop_stream()
                if self._on_playback_done_cb:
                    self._on_playback_done_cb()
                return
            self._current_idx += 1
            idx = self._current_idx
            self._generation += 1
            generation = self._generation

        self._stop_stream()
        self._notify_sentence_change()
        self._play_sentence(idx, generation)

    def prev_sentence(self) -> None:
        with self._lock:
            if self._current_idx > 0:
                self._current_idx -= 1
            # else: restart current sentence (index stays at 0)
            idx = self._current_idx
            self._generation += 1
            generation = self._generation

        self._stop_stream()
        self._notify_sentence_change()
        self._play_sentence(idx, generation)

    def stop(self) -> None:
        with self._lock:
            self._playing = False
            self._stopped = True
            self._generation += 1
        self._stop_stream()
        self._audio_cache.clear()

    def seek_sentence(self, idx: int) -> None:
        with self._lock:
            if not self._sentences:
                return
            clamped_idx = max(0, min(idx, len(self._sentences) - 1))
            self._current_idx = clamped_idx
            generation = self._generation = self._generation + 1
            should_play = self._playing

        self._stop_stream()
        self._notify_sentence_change()
        if should_play:
            self._play_sentence(clamped_idx, generation)

    def set_speed(self, speed: float) -> None:
        with self._lock:
            self._speed = speed

    def set_voice(self, voice: str) -> None:
        with self._lock:
            self._voice = voice

    def on_sentence_change(self, callback) -> None:
        """Register callback: callback(current_idx, total_count)."""
        self._on_sentence_change_cb = callback

    def on_playback_done(self, callback) -> None:
        """Register callback: callback() when all sentences are done."""
        self._on_playback_done_cb = callback

    def on_word_change(self, callback) -> None:
        """Register callback: callback(sentence_idx, total, word_idx, words, sentence_text)."""
        self._on_word_change_cb = callback

    @property
    def current_index(self) -> int:
        return self._current_idx

    @property
    def total_sentences(self) -> int:
        return len(self._sentences)

    @property
    def is_playing(self) -> bool:
        return self._playing

    # -- Internal --

    def _play_sentence(self, idx: int, generation: int, voice: str | None = None, speed: float | None = None) -> None:
        """Fetch audio for sentence idx (if not cached) and play it."""
        with self._lock:
            use_voice = voice or self._voice
            use_speed = speed if speed is not None else self._speed
        threading.Thread(
            target=self._play_sentence_worker, args=(idx, generation, use_voice, use_speed), daemon=True
        ).start()

    def _play_sentence_worker(self, idx: int, generation: int, voice: str, speed: float) -> None:
        with self._lock:
            if self._stopped or generation != self._generation:
                return

        samples = self._get_audio(idx, voice, speed)
        if samples is None:
            # TTS failed — skip to next sentence
            with self._lock:
                if self._stopped or generation != self._generation:
                    return
                if idx < len(self._sentences) - 1:
                    self._current_idx = idx + 1
                    next_idx = self._current_idx
                    self._generation += 1
                    next_generation = self._generation
                else:
                    self._playing = False
                    if self._on_playback_done_cb:
                        self._on_playback_done_cb()
                    return
            self._notify_sentence_change()
            self._play_sentence(next_idx, next_generation)
            return

        # Start pre-fetching next sentence
        if PREFETCH_ENABLED and idx + 1 < len(self._sentences):
            self._prefetch(idx + 1, generation, voice, speed)

        # Play the audio
        with self._lock:
            if self._stopped or self._current_idx != idx or generation != self._generation:
                return  # Navigation happened while we were fetching
            self._current_samples = samples
            self._play_pos = 0

        self._notify_sentence_change()
        initial_word_payload = self._prepare_word_progress(idx, samples)
        if initial_word_payload:
            self._notify_word_change(*initial_word_payload)

        # Create and start output stream
        try:
            finished_event = threading.Event()

            def callback(outdata, frames, time_info, status):
                emit_payload = None
                with self._lock:
                    pos = self._play_pos
                    smp = self._current_samples
                    if smp is None:
                        outdata.fill(0)
                        finished_event.set()
                        return

                    end = pos + frames
                    if end >= len(smp):
                        # Last chunk — pad with zeros
                        remaining = len(smp) - pos
                        if remaining > 0:
                            outdata[:remaining, 0] = smp[pos:len(smp)]
                        outdata[remaining:] = 0
                        self._play_pos = len(smp)
                        finished_event.set()
                    else:
                        outdata[:, 0] = smp[pos:end]
                        self._play_pos = end
                        if self._word_tokens and self._sample_rate > 0:
                            elapsed_s = self._play_pos / self._sample_rate
                            word_idx = self._word_index_for_time(
                                elapsed_s, self._word_end_times_s
                            )
                            if word_idx != self._last_word_idx:
                                self._last_word_idx = word_idx
                                emit_payload = (
                                    self._current_idx,
                                    len(self._sentences),
                                    word_idx,
                                    list(self._word_tokens),
                                    self._sentences[self._current_idx],
                                )
                if emit_payload:
                    self._notify_word_change(*emit_payload)

            stream = sd.OutputStream(
                samplerate=self._sample_rate,
                channels=1,
                dtype='float32',
                callback=callback,
                blocksize=1024,
            )
            with self._lock:
                if self._stopped or self._current_idx != idx or generation != self._generation:
                    return
                self._stream = stream

            stream.start()
            finished_event.wait()
            stream.stop()
            stream.close()

            with self._lock:
                self._stream = None
                self._current_samples = None

                if self._stopped or self._current_idx != idx or generation != self._generation:
                    return

                # Auto-advance to next sentence
                if self._playing and idx == self._current_idx:
                    if idx + 1 < len(self._sentences):
                        self._current_idx += 1
                        next_idx = self._current_idx
                        self._generation += 1
                        next_generation = self._generation
                    else:
                        self._playing = False
                        if self._on_playback_done_cb:
                            self._on_playback_done_cb()
                        return

            self._notify_sentence_change()
            self._play_sentence(next_idx, next_generation)

        except Exception:
            # Audio device error — stop gracefully
            with self._lock:
                self._playing = False
                self._stream = None

    def _get_audio(self, idx: int, voice: str, speed: float) -> np.ndarray | None:
        """Get PCM samples for sentence idx, using cache if available."""
        cache_key = (idx, voice, speed)
        if cache_key in self._audio_cache:
            return self._audio_cache[cache_key]

        wav_bytes = self._tts.synthesize(
            self._sentences[idx], voice, speed
        )
        if wav_bytes is None:
            return None

        samples = self._decode_wav(wav_bytes)
        if samples is not None:
            self._audio_cache[cache_key] = samples
        return samples

    def _decode_wav(self, wav_bytes: bytes) -> np.ndarray | None:
        """Decode WAV bytes to float32 numpy array."""
        try:
            with wave.open(io.BytesIO(wav_bytes), 'rb') as wf:
                self._sample_rate = wf.getframerate()
                n_frames = wf.getnframes()
                raw = wf.readframes(n_frames)
                width = wf.getsampwidth()

            if width == 2:
                samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
                samples /= 32768.0
            elif width == 4:
                samples = np.frombuffer(raw, dtype=np.int32).astype(np.float32)
                samples /= 2147483648.0
            else:
                return None

            return samples
        except Exception:
            return None

    def _prefetch(self, idx: int, generation: int, voice: str, speed: float) -> None:
        """Pre-fetch audio for sentence idx in a background thread."""
        if (idx, voice, speed) in self._audio_cache:
            return
        t = threading.Thread(
            target=self._prefetch_worker, args=(idx, generation, voice, speed), daemon=True
        )
        t.start()
        self._prefetch_thread = t

    def _prefetch_worker(self, idx: int, generation: int, voice: str, speed: float) -> None:
        with self._lock:
            if self._stopped or generation != self._generation:
                return
        self._get_audio(idx, voice, speed)

    def _stop_stream(self) -> None:
        """Stop and close the current audio stream."""
        stream = self._stream
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass
            self._stream = None
        self._current_samples = None
        self._play_pos = 0
        self._word_tokens = []
        self._word_end_times_s = []
        self._last_word_idx = -1

    def _notify_sentence_change(self) -> None:
        if self._on_sentence_change_cb:
            self._on_sentence_change_cb(self._current_idx, len(self._sentences))

    def _notify_word_change(
        self,
        sentence_idx: int,
        total: int,
        word_idx: int,
        words: list[str],
        sentence_text: str,
    ) -> None:
        if self._on_word_change_cb:
            self._on_word_change_cb(sentence_idx, total, word_idx, words, sentence_text)

    def _prepare_word_progress(
        self, sentence_idx: int, samples: np.ndarray
    ) -> tuple[int, int, int, list[str], str] | None:
        sentence_text = self._sentences[sentence_idx]
        words = self._tokenize_sentence(sentence_text)
        duration_s = len(samples) / self._sample_rate if self._sample_rate > 0 else 0.0
        end_times = self._estimate_word_end_times(words, duration_s)

        with self._lock:
            self._word_tokens = words
            self._word_end_times_s = end_times
            self._last_word_idx = 0 if words else -1

        if not words:
            return None
        return (
            sentence_idx,
            len(self._sentences),
            0,
            list(words),
            sentence_text,
        )

    def _tokenize_sentence(self, sentence: str) -> list[str]:
        return sentence.split()

    def _estimate_word_end_times(
        self, words: list[str], duration_s: float
    ) -> list[float]:
        if not words:
            return []
        if duration_s <= 0:
            return [0.0 for _ in words]

        weights = []
        for word in words:
            alnum_len = len(re.sub(r"[^A-Za-z0-9]", "", word))
            weights.append(float(max(alnum_len, 1)))
        total_weight = sum(weights) or float(len(words))

        cumulative = 0.0
        end_times = []
        for weight in weights:
            cumulative += duration_s * (weight / total_weight)
            end_times.append(cumulative)
        if end_times:
            end_times[-1] = duration_s
        return end_times

    def _word_index_for_time(self, elapsed_s: float, end_times_s: list[float]) -> int:
        if not end_times_s:
            return -1
        if elapsed_s <= 0:
            return 0
        for idx, end_s in enumerate(end_times_s):
            if elapsed_s <= end_s:
                return idx
        return len(end_times_s) - 1
