"""Global hotkey listener for Kokoro Reader."""

import threading

from pynput import keyboard

from config import HOTKEY_COMBO


class HotkeyListener:
    def __init__(self, callback):
        """Listen for the configured hotkey and call callback when triggered.

        Ignores rapid presses — if callback is already running, the hotkey is ignored.
        """
        self._callback = callback
        self._processing = False
        self._lock = threading.Lock()
        self._listener = None
        self._hotkey = keyboard.HotKey(
            keyboard.HotKey.parse(HOTKEY_COMBO), self._on_hotkey
        )

    def _on_hotkey(self):
        with self._lock:
            if self._processing:
                return
            self._processing = True

        try:
            self._callback()
        finally:
            with self._lock:
                self._processing = False

    def start(self) -> None:
        def for_canonical(handler):
            # Darwin listener may pass extra metadata args; ignore extras.
            return lambda key, *args: handler(self._listener.canonical(key))

        self._listener = keyboard.Listener(
            on_press=for_canonical(self._hotkey.press),
            on_release=for_canonical(self._hotkey.release),
        )
        self._listener.daemon = True
        self._listener.start()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
