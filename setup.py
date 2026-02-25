"""Build Kokoro Reader as a standalone macOS app via py2app."""

from setuptools import setup

APP = ["reader.py"]
DATA_FILES = []
OPTIONS = {
    "argv_emulation": False,
    "iconfile": None,
    "plist": {
        "CFBundleName": "Kokoro Reader",
        "CFBundleDisplayName": "Kokoro Reader",
        "CFBundleIdentifier": "com.kokoro.reader",
        "CFBundleVersion": "1.0.0",
        "CFBundleShortVersionString": "1.0.0",
        "LSUIElement": True,
    },
    "packages": [
        "rumps",
        "requests",
        "numpy",
        "sounddevice",
        "pynput",
    ],
    "includes": [
        "backend_manager",
        "login_item",
        "tts_client",
        "audio_player",
        "control_panel",
        "hotkey",
        "text_utils",
        "config",
    ],
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
)
