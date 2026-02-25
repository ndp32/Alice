"""Docker-backed Kokoro runtime manager for a turn-key desktop flow."""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass

import tts_client
from config import (
    DOCKER_CONTAINER_NAME,
    DOCKER_IMAGE,
    DOCKER_PORT,
    DOCKER_WAIT_READY_POLL_S,
    DOCKER_WAIT_READY_TIMEOUT_S,
)


@dataclass
class CommandResult:
    ok: bool
    stdout: str = ""
    stderr: str = ""


def _run_command(args: list[str], timeout_s: float = 30) -> CommandResult:
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        return CommandResult(
            ok=(proc.returncode == 0),
            stdout=(proc.stdout or "").strip(),
            stderr=(proc.stderr or "").strip(),
        )
    except (FileNotFoundError, subprocess.SubprocessError) as exc:
        return CommandResult(ok=False, stderr=str(exc))


def _docker_cmd(args: list[str], timeout_s: float = 30) -> CommandResult:
    return _run_command(["docker", *args], timeout_s=timeout_s)


def _docker_available() -> bool:
    return _docker_cmd(["--version"]).ok


def _docker_daemon_running() -> bool:
    return _docker_cmd(["info"], timeout_s=10).ok


def _start_docker_desktop() -> None:
    _run_command(["open", "-a", "Docker"], timeout_s=5)


def _container_names(all_containers: bool) -> set[str]:
    args = ["ps", "--format", "{{.Names}}"]
    if all_containers:
        args.insert(1, "-a")
    result = _docker_cmd(args)
    if not result.ok:
        return set()
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def _container_exists() -> bool:
    return DOCKER_CONTAINER_NAME in _container_names(all_containers=True)


def _container_running() -> bool:
    return DOCKER_CONTAINER_NAME in _container_names(all_containers=False)


def _image_present() -> bool:
    return _docker_cmd(["image", "inspect", DOCKER_IMAGE], timeout_s=10).ok


def _pull_image() -> CommandResult:
    return _docker_cmd(["pull", DOCKER_IMAGE], timeout_s=900)


def _start_or_create_container() -> CommandResult:
    if _container_running():
        return CommandResult(ok=True, stdout="container_running")

    if _container_exists():
        return _docker_cmd(["start", DOCKER_CONTAINER_NAME], timeout_s=30)

    return _docker_cmd(
        [
            "run",
            "-d",
            "--name",
            DOCKER_CONTAINER_NAME,
            "-p",
            f"{DOCKER_PORT}:8880",
            DOCKER_IMAGE,
        ],
        timeout_s=30,
    )


def _wait_for_kokoro_ready(timeout_s: float = DOCKER_WAIT_READY_TIMEOUT_S) -> tuple[bool, str]:
    deadline = time.time() + timeout_s
    last_reason = "unknown"
    while time.time() < deadline:
        reachable, reason = tts_client.check_status()
        if reachable:
            return True, "healthy"
        last_reason = reason
        time.sleep(DOCKER_WAIT_READY_POLL_S)
    return False, f"health_timeout:{last_reason}"


def start_backend() -> tuple[bool, str]:
    if not _docker_available():
        return False, "docker_missing"

    if not _docker_daemon_running():
        _start_docker_desktop()
        for _ in range(15):
            if _docker_daemon_running():
                break
            time.sleep(2)
        else:
            return False, "docker_not_running"

    if not _image_present():
        pull_result = _pull_image()
        if not pull_result.ok:
            err = pull_result.stderr or "pull_failed"
            return False, f"image_pull_failed:{err}"

    start_result = _start_or_create_container()
    if not start_result.ok:
        err = start_result.stderr or "container_start_failed"
        return False, f"container_start_failed:{err}"

    return _wait_for_kokoro_ready()


def ensure_backend_ready() -> tuple[bool, str]:
    reachable, reason = tts_client.check_status()
    if reachable:
        return True, "healthy"
    return start_backend()


def stop_backend() -> tuple[bool, str]:
    if not _docker_available():
        return False, "docker_missing"
    if not _container_exists():
        return True, "container_absent"
    result = _docker_cmd(["stop", DOCKER_CONTAINER_NAME], timeout_s=30)
    if not result.ok:
        err = result.stderr or "container_stop_failed"
        return False, f"container_stop_failed:{err}"
    return True, "container_stopped"


def backend_status() -> dict:
    reachable, health_reason = tts_client.check_status()
    docker_available = _docker_available()
    docker_running = _docker_daemon_running() if docker_available else False

    return {
        "healthy": reachable,
        "reason": health_reason if reachable else ("docker_missing" if not docker_available else health_reason),
        "docker_available": docker_available,
        "docker_running": docker_running,
        "container_running": _container_running() if docker_running else False,
    }
