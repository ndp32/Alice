# Kokoro Reader 🔊

A lightweight macOS menubar app that reads selected text aloud using local AI voices via Kokoro TTS.

Press `⌃⇧Z` anywhere and selected text is spoken. The app now auto-manages the Docker backend in the background.

## One-Time Setup

1. Install Docker Desktop and open it once.
2. Install Python dependencies:
```bash
pip install -r requirements.txt
```
3. Build the `.app` bundle:
```bash
python setup.py py2app
```
4. Move `dist/Kokoro Reader.app` into `/Applications`.
5. Launch the app from Applications (or pin it in Dock).

After this, you do not need to run `docker run` or `python reader.py` manually.

## Daily Use

1. Launch Kokoro Reader (or enable `Launch at Login` in the menu).
2. Wait for menu status `Backend: Ready ✅` / `Kokoro: Connected ✅`.
3. Select text anywhere and press `⌃⇧Z`.
4. Use the floating controls: `⏮`, `⏯`, `⏭`.

## Troubleshooting
- If `Backend: Docker missing ❌`, install Docker Desktop.
- If `Backend: Docker not running ❌`, open Docker Desktop and wait for engine startup.
- If startup fails, use menu `Start Backend` to retry.
- If audio fails, verify nothing else is using port `8880`.
- Ensure Accessibility permission is granted in **System Settings → Privacy & Security → Accessibility**.

## Controls
- **⌃⇧Z** — Read selected text / dismiss panel
- **⏮** — Previous sentence
- **⏯** — Play / Pause
- **⏭** — Next sentence

## Menubar Options
- **Voice** — Switch between voices (af_heart, bf_alice, am_michael, etc.)
- **Speed** — 0.8x, 1.0x, 1.2x, 1.5x
- **Start Backend / Stop Backend** — Manual control of Docker container lifecycle
- **Launch at Login** — Toggle auto-launch at macOS login
- **Status** — Shows backend and Kokoro health

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
