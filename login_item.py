"""Launch-at-login helpers via per-user LaunchAgent plist."""

from __future__ import annotations

import os
import plistlib
import subprocess
import sys
from pathlib import Path

LABEL = "com.kokoro.reader"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def _run(args: list[str], timeout_s: float = 10) -> None:
    try:
        subprocess.run(args, capture_output=True, text=True, timeout=timeout_s, check=False)
    except (FileNotFoundError, subprocess.SubprocessError):
        pass


def default_program_arguments() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable]

    script_path = Path(__file__).resolve().parent / "reader.py"
    return [sys.executable, str(script_path)]


def is_enabled() -> bool:
    return PLIST_PATH.exists()


def enable(program_arguments: list[str] | None = None) -> tuple[bool, str]:
    args = program_arguments or default_program_arguments()
    payload = {
        "Label": LABEL,
        "ProgramArguments": args,
        "RunAtLoad": True,
        "KeepAlive": False,
        "ProcessType": "Background",
        "EnvironmentVariables": {"PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/sbin:/sbin")},
    }

    try:
        PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        with PLIST_PATH.open("wb") as fh:
            plistlib.dump(payload, fh)
    except OSError as exc:
        return False, f"launchagent_write_failed:{exc}"

    _run(["launchctl", "unload", str(PLIST_PATH)])
    _run(["launchctl", "load", str(PLIST_PATH)])
    return True, "enabled"


def disable() -> tuple[bool, str]:
    if not PLIST_PATH.exists():
        return True, "already_disabled"

    _run(["launchctl", "unload", str(PLIST_PATH)])
    try:
        PLIST_PATH.unlink()
    except OSError as exc:
        return False, f"launchagent_remove_failed:{exc}"
    return True, "disabled"
