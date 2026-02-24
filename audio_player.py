"""Audio playback engine with sentence queue, pre-fetching, and navigation."""

import io
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
        self._audio_cache: dict[int, np.ndarray] = {}  # idx -> PCM samples
        self._sample_rate = 24000

        self._stream: sd.OutputStream | None = None
        self._play_pos = 0  # current position in the sample buffer
        self._current_samples: np.ndarray | None = None

        self._playing = False
        self._stopped = False  # True after stop() — no more playback
        self._lock = threading.Lock()

        self._on_sentence_change_cb = None
        self._on_playback_done_cb = None

        self._prefetch_thread: threading.Thread | None = None

    # -- Public API --

    def load_sentences(self, sentences: list[str]) -> None:
        self._sentences = sentences
        self._current_idx = 0
        self._audio_cache.clear()
        self._stopped = False

    def play(self) -> None:
        """Start or resume playback from current sentence."""
        with self._lock:
            if self._stopped or not self._sentences:
                return
            self._playing = True

        # If we have a paused stream with remaining samples, resume it
        if self._stream is not None and self._current_samples is not None:
            self._stream.start()
            return

        # Otherwise, start playing the current sentence
        self._play_sentence(self._current_idx)

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
                self._stop_stream()
                if self._on_playback_done_cb:
                    self._on_playback_done_cb()
                return
            self._current_idx += 1
            idx = self._current_idx

        self._stop_stream()
        self._notify_sentence_change()
        self._play_sentence(idx)

    def prev_sentence(self) -> None:
        with self._lock:
            if self._current_idx > 0:
                self._current_idx -= 1
            # else: restart current sentence (index stays at 0)
            idx = self._current_idx

        self._stop_stream()
        self._notify_sentence_change()
        self._play_sentence(idx)

    def stop(self) -> None:
        with self._lock:
            self._playing = False
            self._stopped = True
        self._stop_stream()
        self._audio_cache.clear()

    def on_sentence_change(self, callback) -> None:
        """Register callback: callback(current_idx, total_count)."""
        self._on_sentence_change_cb = callback

    def on_playback_done(self, callback) -> None:
        """Register callback: callback() when all sentences are done."""
        self._on_playback_done_cb = callback

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

    def _play_sentence(self, idx: int) -> None:
        """Fetch audio for sentence idx (if not cached) and play it."""
        threading.Thread(
            target=self._play_sentence_worker, args=(idx,), daemon=True
        ).start()

    def _play_sentence_worker(self, idx: int) -> None:
        with self._lock:
            if self._stopped:
                return

        samples = self._get_audio(idx)
        if samples is None:
            # TTS failed — skip to next sentence
            with self._lock:
                if idx < len(self._sentences) - 1:
                    self._current_idx = idx + 1
                    next_idx = self._current_idx
                else:
                    self._playing = False
                    if self._on_playback_done_cb:
                        self._on_playback_done_cb()
                    return
            self._notify_sentence_change()
            self._play_sentence(next_idx)
            return

        # Start pre-fetching next sentence
        if PREFETCH_ENABLED and idx + 1 < len(self._sentences):
            self._prefetch(idx + 1)

        # Play the audio
        with self._lock:
            if self._stopped or self._current_idx != idx:
                return  # Navigation happened while we were fetching
            self._current_samples = samples
            self._play_pos = 0

        self._notify_sentence_change()

        # Create and start output stream
        try:
            finished_event = threading.Event()

            def callback(outdata, frames, time_info, status):
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

            stream = sd.OutputStream(
                samplerate=self._sample_rate,
                channels=1,
                dtype='float32',
                callback=callback,
                blocksize=1024,
            )
            with self._lock:
                if self._stopped or self._current_idx != idx:
                    return
                self._stream = stream

            stream.start()
            finished_event.wait()
            stream.stop()
            stream.close()

            with self._lock:
                self._stream = None
                self._current_samples = None

                if self._stopped or self._current_idx != idx:
                    return

                # Auto-advance to next sentence
                if self._playing and idx == self._current_idx:
                    if idx + 1 < len(self._sentences):
                        self._current_idx += 1
                        next_idx = self._current_idx
                    else:
                        self._playing = False
                        if self._on_playback_done_cb:
                            self._on_playback_done_cb()
                        return

            self._notify_sentence_change()
            self._play_sentence(next_idx)

        except Exception:
            # Audio device error — stop gracefully
            with self._lock:
                self._playing = False
                self._stream = None

    def _get_audio(self, idx: int) -> np.ndarray | None:
        """Get PCM samples for sentence idx, using cache if available."""
        if idx in self._audio_cache:
            return self._audio_cache[idx]

        wav_bytes = self._tts.synthesize(
            self._sentences[idx], self._voice, self._speed
        )
        if wav_bytes is None:
            return None

        samples = self._decode_wav(wav_bytes)
        if samples is not None:
            self._audio_cache[idx] = samples
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

    def _prefetch(self, idx: int) -> None:
        """Pre-fetch audio for sentence idx in a background thread."""
        if idx in self._audio_cache:
            return
        t = threading.Thread(target=self._get_audio, args=(idx,), daemon=True)
        t.start()
        self._prefetch_thread = t

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

    def _notify_sentence_change(self) -> None:
        if self._on_sentence_change_cb:
            self._on_sentence_change_cb(self._current_idx, len(self._sentences))
