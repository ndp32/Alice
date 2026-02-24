---
title: "feat: Build Kokoro Reader macOS TTS Menubar App"
type: feat
status: active
date: 2026-02-24
---

# feat: Build Kokoro Reader macOS TTS Menubar App

## Overview

Build a lightweight macOS menubar app that reads selected text aloud using a local Kokoro TTS server. The user presses **⌥⇧Z** anywhere, and selected text is read aloud with a floating control panel for playback navigation. The app runs entirely locally with no cloud dependencies.

## Problem Statement / Motivation

Reading long articles, docs, or emails is time-consuming. A system-wide TTS shortcut that works with any app — using high-quality local AI voices instead of macOS's built-in voices — provides a better listening experience while keeping everything private and offline.

## Proposed Solution

A Python menubar app using `rumps` for the menubar, `PyObjC` for the floating control panel, `pynput` for global hotkeys, and `sounddevice` for audio playback. The app communicates with a separately-installed Kokoro TTS server via HTTP.

### Architecture

```
Global Hotkey (⌥⇧Z)
    → Simulate ⌘C, wait 100ms, read clipboard
    → Split text into sentences
    → Show floating control panel
    → Send sentence to Kokoro TTS → receive WAV bytes
    → Play audio via sounddevice
    → Pre-fetch next sentence while current plays
```

## Implementation Phases

### Phase 1: Core Infrastructure

Build the foundational modules that everything depends on.

#### 1a. `text_utils.py` — Text Processing & Clipboard

- **Sentence splitting:** Split on `. `, `! `, `? `, and newlines. Keep punctuation attached. Filter empties.
- **Clipboard operations:** Read clipboard via `NSPasteboard` (PyObjC). Simulate ⌘C via `CGEventCreateKeyboardEvent` (Quartz).
- **Clipboard preservation:** Save clipboard contents before simulating ⌘C, restore after reading. This prevents destroying the user's clipboard.
- **Stale clipboard detection:** Compare clipboard content before and after ⌘C simulation. If unchanged, treat as "no text selected."

```python
# text_utils.py — key functions
def get_selected_text() -> str | None:
    """Simulate ⌘C, read clipboard, restore previous clipboard contents."""

def split_sentences(text: str) -> list[str]:
    """Split text into sentences on '. ', '! ', '? ', and newlines."""
```

#### 1b. `tts_client.py` — Kokoro API Client

- **Dual endpoint fallback:** Try OpenAI-compatible endpoint first (`localhost:8880/v1/audio/speech`), then Kokori endpoint (`localhost:5002/tts`).
- **HTTP timeouts:** 3s connect timeout, 30s read timeout per request.
- **Health check:** `check_status()` to verify server reachability (used by menubar status indicator).
- **Returns raw WAV bytes** for the audio player to consume.

```python
# tts_client.py — key functions
def synthesize(text: str, voice: str, speed: float) -> bytes | None:
    """Send text to Kokoro TTS, return WAV bytes. Returns None on failure."""

def check_status() -> bool:
    """Check if any Kokoro endpoint is reachable."""
```

#### 1c. `config.py` — Already exists

Configuration is already implemented. Contains endpoints, default voice/speed, hotkey combo, audio format, sample rate, and prefetch setting.

### Phase 2: Audio & Hotkey

#### 2a. `audio_player.py` — Audio Playback Engine

- **Play WAV bytes** via `sounddevice` (decode WAV header, extract PCM data, play).
- **Play/pause/resume:** Use `sounddevice`'s stream with a callback that reads from a buffer. Pause by stopping the stream, resume by restarting from the current position.
- **Sentence queue management:** Track current sentence index, total count.
- **Pre-fetching:** While sentence N plays, fetch audio for sentence N+1 in a background thread using `threading.Thread`.
- **Navigation:** `next_sentence()`, `prev_sentence()`, `stop()`.
- **Callbacks:** Notify the control panel when sentence changes or playback finishes (for UI updates).
- **Thread safety:** Use `threading.Lock` for shared state (current index, playing flag, audio buffer).

```python
# audio_player.py — key class
class AudioPlayer:
    def __init__(self, tts_client, voice, speed):
        ...
    def load_sentences(self, sentences: list[str]): ...
    def play(self): ...
    def pause(self): ...
    def toggle_play_pause(self): ...
    def next_sentence(self): ...
    def prev_sentence(self): ...
    def stop(self): ...
    def on_sentence_change(self, callback): ...  # for UI updates
```

**Edge cases to handle:**
- Next at last sentence: stop playback, keep panel open
- Previous at first sentence: restart current sentence from beginning
- Rapid next/prev clicks: debounce or serialize to avoid race conditions
- Pre-fetch failure: skip failed sentence, attempt next

#### 2b. `hotkey.py` — Global Hotkey Listener

- **Listen for ⌥⇧Z** using `pynput.keyboard.GlobalHotKeys`.
- **Run in a daemon thread** so it doesn't block the main `rumps` event loop.
- **Callback:** Triggers the main app's `on_hotkey()` method.
- **Guard against rapid presses:** Use a simple lock/flag to ignore hotkey if already processing one.

```python
# hotkey.py — key function
class HotkeyListener:
    def __init__(self, callback):
        """Start listening for ⌥⇧Z, call callback when triggered."""
    def start(self): ...
    def stop(self): ...
```

### Phase 3: UI

#### 3a. `control_panel.py` — Floating NSPanel

- **NSPanel** (not NSWindow) with `NSFloatingWindowLevel` so it stays above all windows.
- **Does not steal focus:** Use `NSNonactivatingPanelMask` style so the active app keeps focus.
- **Semi-transparent:** Set background alpha ~0.92.
- **Positioned:** Bottom-center of the main screen.
- **Three buttons:** ⏮ (previous), ⏯ (play/pause), ⏭ (next).
- **Progress label:** "Sentence 3 of 12".
- **Close button:** Dismisses panel and stops playback.
- **Must update on main thread:** All UI updates dispatched via `performSelectorOnMainThread:` or `NSOperationQueue.mainQueue()`.

```python
# control_panel.py — key class
class ControlPanel:
    def __init__(self):
        """Create the floating NSPanel with buttons and label."""
    def show(self): ...
    def hide(self): ...
    def update_progress(self, current: int, total: int): ...
    def set_playing(self, is_playing: bool): ...  # toggle button icon
    def set_callbacks(self, on_prev, on_toggle, on_next, on_close): ...
```

### Phase 4: Main App — Tying It All Together

#### 4a. `reader.py` — Entry Point

- **`rumps.App`** subclass with menubar icon (🔊 or speaker character).
- **Menu items:**
  - Voice submenu: af_heart, bf_alice, am_michael (checkmark on selected)
  - Speed submenu: 0.8x, 1.0x, 1.2x, 1.5x (checkmark on selected)
  - Kokoro Status: "Connected ✅" or "Not found ❌" (check on startup + periodically)
  - Quit
- **Hotkey callback (`on_hotkey`):**
  1. If already playing → stop playback, hide panel (toggle behavior)
  2. If not playing → call `get_selected_text()`, if None show "No text selected" notification
  3. Split into sentences, create AudioPlayer, show control panel, start playback
- **Wire up:** control panel callbacks → audio player methods, audio player sentence-change callback → control panel update
- **Kokoro status polling:** Timer every 30s to check server reachability, update menu item
- **Notifications:** Use `rumps.notification()` for error messages

```python
# reader.py — main structure
class KokoroReaderApp(rumps.App):
    def __init__(self):
        super().__init__("🔊", quit_button=None)
        # Set up menu, hotkey listener, TTS client

    def on_hotkey(self):
        """Called when ⌥⇧Z is pressed."""

    @rumps.timer(30)
    def check_kokoro_status(self, _):
        """Periodically check if Kokoro TTS is reachable."""

if __name__ == "__main__":
    KokoroReaderApp().run()
```

## Implementation Order

Build and test incrementally:

1. **`text_utils.py`** — No dependencies, easy to unit test
2. **`tts_client.py`** — Needs a running Kokoro server to integration test, but logic is straightforward
3. **`audio_player.py`** — Depends on `tts_client`. Test with hardcoded WAV data first
4. **`hotkey.py`** — Independent, test with print callbacks
5. **`control_panel.py`** — Independent PyObjC code, test standalone
6. **`reader.py`** — Integrates everything, test end-to-end

## Technical Considerations

### Threading Model

- **Main thread:** `rumps` event loop (which is the `NSApplication` run loop). All PyObjC/UI operations must happen here.
- **Hotkey thread:** `pynput` listener runs in a daemon thread.
- **Audio thread:** `sounddevice` runs its own callback thread for playback.
- **Pre-fetch thread:** Background thread for HTTP requests to Kokoro.
- **Critical:** HTTP requests and audio operations must NOT block the main thread. Use `threading.Thread` for all I/O. Dispatch UI updates back to main thread.

### Clipboard Handling (SpecFlow Gap)

The spec says "simulate ⌘C to copy" but doesn't address clipboard preservation. The implementation should:
1. Save current clipboard contents (`NSPasteboard.generalPasteboard()`)
2. Clear clipboard
3. Simulate ⌘C
4. Wait 100ms
5. Read new clipboard contents
6. Restore original clipboard contents
7. If clipboard didn't change after ⌘C → no text was selected

### Hotkey-While-Playing Behavior (SpecFlow Gap)

The spec says "Press ⌥⇧Z again to dismiss and stop playback." Implementation: if playback is active when hotkey fires, stop playback and hide panel. If not active, start the normal flow. This is a simple toggle.

### Race Condition Prevention (SpecFlow Gap)

- **Rapid hotkey presses:** Use a `threading.Lock` in the hotkey handler. If already processing, ignore.
- **Rapid next/prev clicks:** Serialize navigation operations. Cancel any in-flight TTS request before starting a new one.

### HTTP Timeouts (SpecFlow Gap)

All `requests` calls must have explicit timeouts: `timeout=(3, 30)` (3s connect, 30s read). Without this, a hung server would freeze the app.

## Acceptance Criteria

- [ ] ⌥⇧Z copies selected text and starts reading it aloud
- [ ] Floating control panel appears with ⏮ ⏯ ⏭ buttons and progress label
- [ ] Panel floats above all windows without stealing focus
- [ ] Play/pause works correctly
- [ ] Next/previous sentence navigation works (including boundary cases)
- [ ] ⌥⇧Z again dismisses panel and stops playback
- [ ] Pre-fetches next sentence audio while current plays
- [ ] Menubar shows voice selection, speed control, and Kokoro status
- [ ] Changing voice/speed affects subsequent sentences
- [ ] "No text selected" notification when nothing is selected
- [ ] "Kokoro TTS not found" notification when server is down
- [ ] Failed sentences are skipped gracefully
- [ ] Clipboard is preserved (not destroyed by ⌘C simulation)
- [ ] No main thread blocking — UI stays responsive during TTS requests
- [ ] App exits cleanly via menubar Quit

## Dependencies & Risks

| Risk | Mitigation |
|------|-----------|
| macOS Accessibility permission required | Clear instructions in README; notification on first run |
| `rumps` + PyObjC threading conflicts | All UI on main thread; I/O on background threads |
| Kokoro server not installed | Graceful error notification; status indicator in menubar |
| `sounddevice` platform issues | WAV playback is well-supported on macOS; fallback: document `portaudio` installation |
| `pynput` accessibility requirement | Same permission as ⌘C simulation; one permission covers both |

## File Structure

```
kokoro-reader/
├── reader.py          # Main app entry point (rumps.App)
├── tts_client.py      # Kokoro API client (HTTP, fallback)
├── audio_player.py    # Audio playback (sounddevice, sentence queue, prefetch)
├── control_panel.py   # Floating NSPanel (PyObjC)
├── hotkey.py          # Global hotkey listener (pynput)
├── text_utils.py      # Sentence splitting, clipboard ops
├── config.py          # Configuration constants (already exists)
├── requirements.txt   # Dependencies (already exists)
└── README.md          # Setup instructions (already exists)
```

## Sources & References

- SPEC.md — Full technical specification (`/Users/nikopaulson/Documents/Alice/SPEC.md`)
- config.py — Existing configuration (`/Users/nikopaulson/Documents/Alice/config.py`)
- SpecFlow analysis identified 5 critical gaps (clipboard preservation, hotkey toggle, race conditions, HTTP timeouts, stale clipboard detection) — all addressed in Technical Considerations above
