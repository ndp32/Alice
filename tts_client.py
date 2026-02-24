"""Kokoro TTS API client with dual endpoint fallback."""

import requests

from config import KOKORO_ENDPOINTS

# Timeouts: 3s connect, 30s read
TIMEOUT = (3, 30)


def synthesize(text: str, voice: str, speed: float) -> bytes | None:
    """Send text to Kokoro TTS, return WAV bytes.

    Tries each configured endpoint in order. Returns None on failure.
    """
    for endpoint in KOKORO_ENDPOINTS:
        url = endpoint["url"]
        fmt = endpoint["payload_format"]

        if fmt == "openai":
            payload = {
                "input": text,
                "voice": voice,
                "speed": speed,
                "response_format": "wav",
            }
        else:  # kokori
            payload = {
                "text": text,
                "voice": voice,
                "speed": speed,
            }

        try:
            resp = requests.post(url, json=payload, timeout=TIMEOUT)
            if resp.status_code == 200 and len(resp.content) > 0:
                return resp.content
        except requests.RequestException:
            continue

    return None


def check_status() -> bool:
    """Check if any Kokoro endpoint is reachable."""
    for endpoint in KOKORO_ENDPOINTS:
        url = endpoint["url"]
        # Try a HEAD or GET to the base URL to check reachability.
        # For the OpenAI endpoint, the base is the speech endpoint itself.
        try:
            resp = requests.get(url, timeout=(3, 5))
            # Any response (even 4xx) means the server is up
            return True
        except requests.RequestException:
            continue
    return False
