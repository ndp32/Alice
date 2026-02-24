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

# Default voice (Kokoro voice ID)
# Good options: af_heart (best female US), bf_alice (best female UK), am_michael (male US)
DEFAULT_VOICE = "af_heart"

# Default speed (1.0 = normal)
DEFAULT_SPEED = 1.0

# Global hotkey
HOTKEY_COMBO = "<alt>+<shift>+z"

# Audio format
AUDIO_FORMAT = "wav"
SAMPLE_RATE = 24000

# Pre-fetch next sentence while current one plays
PREFETCH_ENABLED = True
