---
title: "feat: Reliable Select-Text Hotkey Flow for Kokoro Reader"
type: feat
status: active
date: 2026-02-25
---

# feat: Reliable Select-Text Hotkey Flow for Kokoro Reader

## Summary
Harden the existing menubar app flow so selecting text and pressing `⌥⇧Z` works consistently across macOS apps, while reducing API noise and improving playback/control stability.

## Goals
- Trigger TTS reliably from selected text via global hotkey.
- Remove health-check traffic that hits `/v1/audio/speech` with `GET`.
- Keep UI updates thread-safe from hotkey/audio worker threads.
- Stabilize playback transitions under rapid control inputs.
- Add unit tests for endpoint probing, text selection behavior, and player state transitions.

## Scope
- In scope: `reader.py`, `tts_client.py`, `text_utils.py`, `audio_player.py`, `config.py`, tests, and README updates.
- Out of scope: notarization, packaging, new UI surfaces, cloud fallback providers.

## Interface Changes
- `tts_client.check_status(mode: str = "cheap") -> tuple[bool, str]`
  - `cheap`: probes `KOKORO_HEALTH_URLS`.
  - `full`: performs tiny synth probe.
  - Returns `(reachable, reason)`.
- `text_utils.get_selected_text(copy_delay_s: float = 0.15, min_chars: int = 1) -> str | None`
  - Allows timing control and stronger empty-selection handling.

## Implementation Details

### 1) Endpoint and status hardening
- Add `KOKORO_HEALTH_URLS` in config and probe those URLs only.
- Keep synthesis endpoint list for actual POST requests.
- Add timeout constants for synth and health checks.
- Return detailed status reason from health checks.

### 2) Selection reliability
- Normalize repeated blank lines before sentence splitting.
- Treat whitespace-only clipboard capture as no selection.
- Return `None` when copied text is unchanged from original clipboard content.
- Restore clipboard text after capture.

### 3) Main-thread UI safety
- Route notifications through main queue dispatch helper.
- Route status menu title updates through main queue.
- Keep control panel updates via main queue operations.

### 4) Playback concurrency stabilization
- Add playback generation token to invalidate stale workers after nav/stop.
- Ensure stale prefetch workers do not mutate active playback state.
- Keep lock-scoped transitions for `play`, `next`, `prev`, `stop`.

### 5) Test coverage
- `tests/test_tts_client.py`
  - Health checks use health URLs.
  - Failure reason classification.
  - Endpoint fallback behavior.
- `tests/test_text_utils.py`
  - Sentence splitting with punctuation/newline cases.
  - Whitespace/unchanged clipboard selection rejection.
  - Trimmed selected text behavior.
- `tests/test_audio_player_state.py`
  - Prev/next boundary behavior.
  - Playback done callback when next at end.
  - Stale prefetch worker ignored by generation token.

## Acceptance Criteria
- App status updates to connected/not-found without 405 spam from app-generated health checks.
- Selected text reads after pressing `⌥⇧Z`.
- No crashes/races during rapid control interaction.
- Unit tests pass in a configured dev environment.

## Assumptions
- Local Kokoro API is available at `http://localhost:8880`.
- Current default voice and hotkey remain unchanged.
- Text clipboard restoration is sufficient for v1 (rich clipboard formats deferred).
