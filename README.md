# Kokoro Reader 🔊

A lightweight macOS menubar app that reads selected text aloud using local AI voices via [Kokoro TTS](https://github.com/hexgrad/kokoro).

**Press ⌥⇧Z anywhere** → selected text is read aloud with natural AI voices. Completely local, completely private.

## Quick Start

### 1. Start a Kokoro TTS server

**Easiest:** Download [Kokori](https://kokori.app) — open it and the server runs automatically.

**Free:** Run via Docker:
```bash
docker run -p 8880:8880 ghcr.io/remsky/kokoro-fastapi-cpu:v0.2.4
```

### 2. Install Kokoro Reader
```bash
pip install -r requirements.txt
python reader.py
```

### 3. Grant Accessibility Permission
macOS will prompt you. Go to **System Settings → Privacy & Security → Accessibility** and enable your terminal app or Python.

### 4. Use It
Select text anywhere. Press **⌥⇧Z**. A control panel appears with ⏮ ⏯ ⏭ buttons.

## Troubleshooting
- If you see `405 Method Not Allowed` on `GET /v1/audio/speech`, that's expected for browser-style requests. TTS generation must use `POST`.
- First synthesis request may be slower while the model warms up.
- Ensure Accessibility permission is granted: **System Settings -> Privacy & Security -> Accessibility**.
- If audio fails, verify nothing else is using port `8880`.

## Controls
- **⌥⇧Z** — Read selected text / dismiss panel
- **⏮** — Previous sentence
- **⏯** — Play / Pause
- **⏭** — Next sentence

## Menubar Options
- **Voice** — Switch between voices (af_heart, bf_alice, am_michael, etc.)
- **Speed** — 0.8x, 1.0x, 1.2x, 1.5x
- **Status** — Shows whether Kokoro server is reachable

## Voices
Best quality voices from Kokoro:
| Voice | Description | Quality |
|-------|------------|---------|
| af_heart | American female | A (best) |
| bf_alice | British female | A |
| bf_emma | British female | A- |
| af_bella | American female | A- |
| am_michael | American male | C+ |
| am_fenrir | American male | C+ |
| bm_daniel | British male | B |
