# Kokoro Reader — Configuration

# Kokoro TTS server endpoints (tried in order)
KOKORO_ENDPOINTS = [
    {
        "url": "http://localhost:8880/v1/audio/speech",
        "payload_format": "openai",  # {"input": ..., "voice": ..., "speed": ..., "response_format": "wav"}
    },
    {
        "url": "http://localhost:5002/tts",
        "payload_format": "kokori",  # {"text": ..., "voice": ..., "speed": ...}
    },
]

# Health URLs used for low-cost reachability checks.
# Avoid probing /v1/audio/speech with GET to prevent 405 log spam.
KOKORO_HEALTH_URLS = [
    "http://localhost:8880/web/",
    "http://localhost:5002/",
]

# Default voice (Kokoro voice ID)
# Good options: af_heart (best female US), bf_alice (best female UK), am_michael (male US)
DEFAULT_VOICE = "bf_emma"

# Default speed (1.0 = normal)
DEFAULT_SPEED = 1.0

# Global hotkey
HOTKEY_COMBO = "<ctrl>+<shift>+z"

# Audio format
AUDIO_FORMAT = "wav"
SAMPLE_RATE = 24000

# Pre-fetch next sentence while current one plays
PREFETCH_ENABLED = True

# HTTP timeouts
REQUEST_TIMEOUT_CONNECT_S = 3
REQUEST_TIMEOUT_READ_S = 30
HEALTH_TIMEOUT_CONNECT_S = 2
HEALTH_TIMEOUT_READ_S = 3

# Docker backend automation
DOCKER_IMAGE = "ghcr.io/remsky/kokoro-fastapi-cpu:v0.2.4"
DOCKER_CONTAINER_NAME = "kokoro-reader-tts"
DOCKER_PORT = 8880
DOCKER_WAIT_READY_TIMEOUT_S = 90
DOCKER_WAIT_READY_POLL_S = 2
