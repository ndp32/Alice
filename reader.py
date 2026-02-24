"""Kokoro Reader — macOS menubar TTS app."""

import threading

import rumps

import tts_client
from audio_player import AudioPlayer
from config import DEFAULT_SPEED, DEFAULT_VOICE
from control_panel import ControlPanel
from hotkey import HotkeyListener
from text_utils import get_selected_text, split_sentences

VOICES = ["af_heart", "bf_alice", "am_michael"]
SPEEDS = [0.8, 1.0, 1.2, 1.5]


class KokoroReaderApp(rumps.App):
    def __init__(self):
        super().__init__("🔊", quit_button=None)

        self._voice = DEFAULT_VOICE
        self._speed = DEFAULT_SPEED
        self._player: AudioPlayer | None = None
        self._panel: ControlPanel | None = None
        self._hotkey = HotkeyListener(self._on_hotkey)

        self._build_menu()
        self._hotkey.start()

    def _build_menu(self):
        # Voice submenu
        voice_menu = rumps.MenuItem("Voice")
        for v in VOICES:
            item = rumps.MenuItem(v, callback=self._on_voice_select)
            if v == self._voice:
                item.state = 1
            voice_menu.add(item)

        # Speed submenu
        speed_menu = rumps.MenuItem("Speed")
        for s in SPEEDS:
            label = f"{s}x"
            item = rumps.MenuItem(label, callback=self._on_speed_select)
            if s == self._speed:
                item.state = 1
            speed_menu.add(item)

        # Status
        self._status_item = rumps.MenuItem("Kokoro: checking...")
        self._status_item.set_callback(None)

        self.menu = [
            voice_menu,
            speed_menu,
            None,  # separator
            self._status_item,
            None,
            rumps.MenuItem("Quit", callback=self._on_quit),
        ]

    def _on_voice_select(self, sender):
        self._voice = sender.title
        # Update checkmarks
        voice_menu = self.menu["Voice"]
        for key in voice_menu:
            voice_menu[key].state = 1 if key == sender.title else 0

    def _on_speed_select(self, sender):
        self._speed = float(sender.title.rstrip("x"))
        speed_menu = self.menu["Speed"]
        for key in speed_menu:
            speed_menu[key].state = 1 if key == sender.title else 0

    def _on_quit(self, _):
        self._cleanup()
        rumps.quit_application()

    def _cleanup(self):
        if self._player:
            self._player.stop()
        if self._panel:
            self._panel.hide()
        self._hotkey.stop()

    def _on_hotkey(self):
        """Called when ⌥⇧Z is pressed. Runs on hotkey thread."""
        # Toggle: if playing, stop
        if self._player and self._player.is_playing:
            self._stop_playback()
            return

        # Get selected text
        text = get_selected_text()
        if not text:
            rumps.notification(
                "Kokoro Reader", "", "No text selected.", sound=False
            )
            return

        sentences = split_sentences(text)
        if not sentences:
            rumps.notification(
                "Kokoro Reader", "", "No text selected.", sound=False
            )
            return

        # Check server
        if not tts_client.check_status():
            rumps.notification(
                "Kokoro Reader",
                "",
                "Kokoro TTS not found. Start the Kokoro server first.",
                sound=False,
            )
            return

        # Start playback
        self._start_playback(sentences)

    def _start_playback(self, sentences: list[str]):
        # Stop any existing playback
        if self._player:
            self._player.stop()

        # Create panel if needed (lazy init — must happen after NSApp is running)
        if self._panel is None:
            self._panel = ControlPanel()

        player = AudioPlayer(tts_client, self._voice, self._speed)
        player.load_sentences(sentences)
        player.on_sentence_change(self._on_sentence_change)
        player.on_playback_done(self._on_playback_done)
        self._player = player

        self._panel.set_callbacks(
            on_prev=player.prev_sentence,
            on_toggle=player.toggle_play_pause,
            on_next=player.next_sentence,
            on_close=self._stop_playback,
        )
        self._panel.update_progress(0, len(sentences))
        self._panel.set_playing(True)
        self._panel.show()

        player.play()

    def _stop_playback(self):
        if self._player:
            self._player.stop()
            self._player = None
        if self._panel:
            self._panel.hide()

    def _on_sentence_change(self, current_idx: int, total: int):
        if self._panel:
            self._panel.update_progress(current_idx, total)

    def _on_playback_done(self):
        if self._panel:
            self._panel.set_playing(False)

    @rumps.timer(30)
    def _check_kokoro_status(self, _):
        """Periodically check if Kokoro TTS is reachable."""
        def _check():
            reachable = tts_client.check_status()
            label = "Kokoro: Connected ✅" if reachable else "Kokoro: Not found ❌"
            self._status_item.title = label

        threading.Thread(target=_check, daemon=True).start()


if __name__ == "__main__":
    KokoroReaderApp().run()
