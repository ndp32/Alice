"""Kokoro TTS API client with endpoint fallback and health checks."""

import requests

from config import (
    HEALTH_TIMEOUT_CONNECT_S,
    HEALTH_TIMEOUT_READ_S,
    KOKORO_ENDPOINTS,
    KOKORO_HEALTH_URLS,
    REQUEST_TIMEOUT_CONNECT_S,
    REQUEST_TIMEOUT_READ_S,
)

# Timeouts
SYNTH_TIMEOUT = (REQUEST_TIMEOUT_CONNECT_S, REQUEST_TIMEOUT_READ_S)
HEALTH_TIMEOUT = (HEALTH_TIMEOUT_CONNECT_S, HEALTH_TIMEOUT_READ_S)


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
            resp = requests.post(url, json=payload, timeout=SYNTH_TIMEOUT)
            if resp.status_code == 200 and len(resp.content) > 0:
                return resp.content
        except requests.RequestException:
            continue

    return None


def _classify_request_error(exc: requests.RequestException) -> str:
    msg = str(exc).lower()
    if "timed out" in msg:
        return "timeout"
    if "connection refused" in msg:
        return "connection_refused"
    return "request_error"


def check_status(mode: str = "cheap") -> tuple[bool, str]:
    """Check if any Kokoro endpoint is reachable.

    Args:
        mode: "cheap" probes lightweight health URLs; "full" performs a
            minimal synthesis probe.

    Returns:
        tuple[bool, str]: (reachable, reason).
    """
    if mode == "full":
        audio = synthesize("hi", "af_heart", 1.0)
        if audio:
            return True, "synthesis_ok"
        return False, "synthesis_failed"

    last_reason = "no_endpoints_reachable"
    for url in KOKORO_HEALTH_URLS:
        try:
            resp = requests.get(url, timeout=HEALTH_TIMEOUT)
            if resp.status_code < 500:
                return True, f"http_{resp.status_code}"
            last_reason = f"http_{resp.status_code}"
        except requests.RequestException as exc:
            last_reason = _classify_request_error(exc)
            continue

    return False, last_reason
