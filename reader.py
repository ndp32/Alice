"""Kokoro Reader — macOS menubar TTS app."""

import threading

import rumps
from AppKit import NSBlockOperation, NSOperationQueue

import backend_manager
import login_item
import tts_client
from audio_player import AudioPlayer
from config import DEFAULT_SPEED, DEFAULT_VOICE
from control_panel import ControlPanel
from hotkey import HotkeyListener
from text_utils import get_selected_text, has_accessibility_permission, split_sentences

VOICES = ["af_heart", "bf_alice", "bf_emma", "am_michael"]
SPEEDS = [0.8, 1.0, 1.2, 1.5]


class KokoroReaderApp(rumps.App):
    def __init__(self):
        super().__init__("🔊", quit_button=None)

        self._voice = DEFAULT_VOICE
        self._speed = DEFAULT_SPEED
        self._player: AudioPlayer | None = None
        self._panel: ControlPanel | None = None
        self._hotkey = HotkeyListener(self._on_hotkey)
        self._backend_starting = False

        self._build_menu()
        self._hotkey.start()
        self._refresh_login_item_state()
        threading.Thread(target=self._ensure_backend_on_launch, daemon=True).start()

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
        self._backend_item = rumps.MenuItem("Backend: checking...")
        self._backend_item.set_callback(None)
        self._launch_item = rumps.MenuItem("Launch at Login", callback=self._toggle_launch_at_login)

        self.menu = [
            voice_menu,
            speed_menu,
            None,  # separator
            self._backend_item,
            self._status_item,
            rumps.MenuItem("Start Backend", callback=self._start_backend_from_menu),
            rumps.MenuItem("Stop Backend", callback=self._stop_backend_from_menu),
            self._launch_item,
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
        """Called when ⌃⇧Z is pressed. Runs on hotkey thread."""
        if not has_accessibility_permission():
            self._notify(
                "Grant Accessibility to Kokoro Reader in System Settings -> Privacy & Security -> Accessibility."
            )
            return

        # Toggle: if playing, stop
        if self._player and self._player.is_playing:
            self._run_on_main(self._stop_playback)
            return

        # Get selected text
        text = get_selected_text()
        if not text:
            self._notify("No text selected.")
            return

        sentences = split_sentences(text)
        if not sentences:
            self._notify("No text selected.")
            return

        # Check backend and recover automatically if needed
        reachable, reason = backend_manager.ensure_backend_ready()
        if not reachable:
            self._notify(f"Kokoro backend unavailable: {reason}")
            return

        # Start playback
        self._run_on_main(lambda: self._start_playback(sentences))

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
            self._panel.set_playing(False)
            self._panel.hide()

    def _notify(self, message: str) -> None:
        def _safe_notify():
            try:
                rumps.notification("Kokoro Reader", "", message, sound=False)
            except Exception:
                # pyenv Python builds may not have Info.plist/CFBundleIdentifier.
                # In that case, skip macOS notification instead of crashing.
                print(f"[Kokoro Reader] {message}", flush=True)

        self._run_on_main(_safe_notify)

    def _run_on_main(self, block) -> None:
        op = NSBlockOperation.blockOperationWithBlock_(block)
        NSOperationQueue.mainQueue().addOperation_(op)

    def _on_sentence_change(self, current_idx: int, total: int):
        if self._panel:
            self._panel.update_progress(current_idx, total)

    def _on_playback_done(self):
        if self._panel:
            self._panel.set_playing(False)

    def _set_backend_starting(self, value: bool) -> None:
        def _set():
            self._backend_starting = value
            if value:
                self._backend_item.title = "Backend: starting..."

        self._run_on_main(_set)

    def _ensure_backend_on_launch(self):
        self._set_backend_starting(True)
        ok, reason = backend_manager.ensure_backend_ready()
        self._set_backend_starting(False)
        if not ok:
            self._notify(f"Backend startup failed: {reason}")
        self._refresh_backend_status()

    def _refresh_backend_status(self):
        status = backend_manager.backend_status()
        if status["healthy"]:
            kokoro_label = "Kokoro: Connected ✅"
            backend_label = "Backend: Ready ✅"
        else:
            kokoro_label = f"Kokoro: Not found ❌ ({status['reason']})"
            if not status["docker_available"]:
                backend_label = "Backend: Docker missing ❌"
            elif not status["docker_running"]:
                backend_label = "Backend: Docker not running ❌"
            elif status["container_running"]:
                backend_label = "Backend: Container up, health failing ❌"
            else:
                backend_label = "Backend: Container stopped ❌"

        def _set_labels():
            self._status_item.title = kokoro_label
            if self._backend_starting:
                self._backend_item.title = "Backend: starting..."
            else:
                self._backend_item.title = backend_label

        self._run_on_main(_set_labels)

    def _start_backend_from_menu(self, _):
        def _work():
            self._set_backend_starting(True)
            ok, reason = backend_manager.start_backend()
            self._set_backend_starting(False)
            if not ok:
                self._notify(f"Failed to start backend: {reason}")
            self._refresh_backend_status()

        threading.Thread(target=_work, daemon=True).start()

    def _stop_backend_from_menu(self, _):
        def _work():
            ok, reason = backend_manager.stop_backend()
            if not ok:
                self._notify(f"Failed to stop backend: {reason}")
            self._refresh_backend_status()

        threading.Thread(target=_work, daemon=True).start()

    def _refresh_login_item_state(self):
        enabled = login_item.is_enabled()

        def _set():
            self._launch_item.state = 1 if enabled else 0

        self._run_on_main(_set)

    def _toggle_launch_at_login(self, _):
        currently_enabled = login_item.is_enabled()
        if currently_enabled:
            ok, reason = login_item.disable()
            if not ok:
                self._notify(f"Launch-at-login disable failed: {reason}")
        else:
            ok, reason = login_item.enable()
            if not ok:
                self._notify(f"Launch-at-login enable failed: {reason}")
        self._refresh_login_item_state()

    @rumps.timer(30)
    def _check_kokoro_status(self, _):
        """Periodically check if Kokoro TTS is reachable."""
        def _check():
            self._refresh_backend_status()

        threading.Thread(target=_check, daemon=True).start()


if __name__ == "__main__":
    KokoroReaderApp().run()
