# Kokoro Reader — macOS TTS Widget

## What This Is
A lightweight macOS menubar app that reads selected text aloud using a local Kokoro TTS server. Press **⌥⇧Z** anywhere on your Mac, and the currently selected text gets read aloud with a high-quality AI voice. A small floating control panel provides play/pause, forward (next sentence), and backward (previous sentence) controls.

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────┐
│  Global Hotkey   │────▶│  Kokoro Reader   │────▶│ Kokoro TTS  │
│  ⌥⇧Z            │     │  (this app)      │     │ localhost:  │
└─────────────────┘     │                  │◀────│ 8880        │
                        │  Control Panel:  │     └─────────────┘
                        │  ◀◀  ▶/⏸  ▶▶    │
                        └──────────────────┘
```

### Components
1. **Kokoro TTS Server** — User installs separately (kokoro-fastapi or Kokori app). Runs at `http://localhost:8880/v1/audio/speech` (OpenAI-compatible endpoint).
2. **Kokoro Reader** (this app) — Python menubar app that:
   - Listens for global hotkey ⌥⇧Z
   - Copies selected text via simulated ⌘C
   - Splits text into sentences
   - Sends each sentence to Kokoro TTS
   - Plays audio with a floating control panel

## Dependencies

```
pip install rumps pyobjc-framework-Cocoa pyobjc-framework-Quartz pynput requests sounddevice numpy
```

- `rumps` — menubar app framework
- `pyobjc-framework-Cocoa` / `pyobjc-framework-Quartz` — native macOS integration (floating panel, clipboard)
- `pynput` — global hotkey listener
- `requests` — HTTP calls to Kokoro API
- `sounddevice` + `numpy` — audio playback
- Python 3.10+

## Kokoro TTS API

The app should target the OpenAI-compatible endpoint that kokoro-fastapi exposes:

```
POST http://localhost:8880/v1/audio/speech
Content-Type: application/json

{
  "input": "Text to speak",
  "voice": "af_heart",
  "speed": 1.0,
  "response_format": "wav"
}

Response: audio/wav binary
```

If that fails, fall back to trying:
```
POST http://localhost:5002/tts
Content-Type: application/json

{
  "text": "Text to speak",
  "voice": "af_heart",
  "speed": 1.0
}
```
(This is the Kokori app's endpoint.)

## Behavior

### Hotkey Trigger (⌥⇧Z)
1. Simulate ⌘C to copy selected text
2. Wait 100ms, read clipboard
3. If clipboard has text, split into sentences
4. Show the floating control panel
5. Start playing from sentence 0

### Sentence Splitting
Split on `. `, `! `, `? `, and newlines. Keep the punctuation attached to the sentence. Filter out empty strings.

### Control Panel (floating window)
- Always-on-top, small, semi-transparent
- Positioned near bottom-center of screen
- Three buttons: **⏮** (previous sentence), **⏯** (play/pause), **⏭** (next sentence)
- Text label showing: "Sentence 3 of 12" (current progress)
- Click anywhere else and the panel stays visible (always on top)
- Press ⌥⇧Z again or click X to dismiss and stop playback

### Audio Playback
- Pre-fetch: while sentence N is playing, fetch audio for sentence N+1 in background
- On play: send sentence text to Kokoro, get wav back, play via sounddevice
- On pause: pause sounddevice playback
- Forward: stop current, advance to next sentence, play
- Backward: go to previous sentence, play

### Menubar
- Simple icon (🔊 or a speaker symbol)
- Menu items:
  - Voice: [submenu with a few good defaults: af_heart, bf_alice, am_michael]
  - Speed: [0.8x, 1.0x, 1.2x, 1.5x]
  - Kokoro Status: Connected ✅ / Not found ❌
  - Quit

### Error Handling
- If Kokoro server is not running: show macOS notification "Kokoro TTS not found. Start the Kokoro server first."
- If no text is selected: show notification "No text selected"
- If audio generation fails for a sentence: skip it and move to next

## File Structure

```
kokoro-reader/
├── reader.py          # Main app entry point
├── tts_client.py      # Kokoro API client
├── audio_player.py    # Audio playback with play/pause/seek
├── control_panel.py   # Floating NSWindow control panel
├── hotkey.py          # Global hotkey listener
├── text_utils.py      # Sentence splitting, clipboard
├── config.py          # Voice, speed, server URL defaults
├── requirements.txt
└── README.md          # Setup instructions
```

## Setup Instructions (for README.md)

### 1. Install Kokoro TTS Server
Option A (easiest): Download Kokori from kokori.app — just open it and the server runs.

Option B (free): Install kokoro-fastapi:
```bash
# Using Docker:
docker run -p 8880:8880 ghcr.io/remsky/kokoro-fastapi-cpu:latest

# Or using pip:
pip install kokoro-fastapi
kokoro-fastapi --port 8880
```

### 2. Install Kokoro Reader
```bash
cd kokoro-reader
pip install -r requirements.txt
python reader.py
```

### 3. Grant Permissions
On first run, macOS will ask for:
- **Accessibility** permission (for the global hotkey and simulating ⌘C)
- Go to System Settings → Privacy & Security → Accessibility → enable Terminal / Python

### 4. Use It
Select any text anywhere on your Mac. Press **⌥⇧Z**. Listen.

## Notes for Claude Code
- This needs to run on macOS. Use native macOS APIs via PyObjC where needed.
- The floating control panel should be an NSPanel (or NSWindow with appropriate level) so it floats above other windows without taking focus.
- For the hotkey, pynput's GlobalHotKeys is the simplest approach. The combination is `<alt>+<shift>+z`.
- Test with `say` command first if Kokoro isn't available, to verify the pipeline works.
- Keep it simple. No databases, no web frameworks, no over-engineering.
