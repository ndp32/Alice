"""Text processing and clipboard operations for Kokoro Reader."""

import re
import time

from ApplicationServices import AXIsProcessTrusted
from AppKit import NSPasteboard, NSStringPboardType
from Quartz import (
    CGEventCreateKeyboardEvent,
    CGEventPost,
    CGEventSetFlags,
    kCGEventFlagMaskCommand,
    kCGHIDEventTap,
)


def split_sentences(text: str) -> list[str]:
    """Split text into sentences on '. ', '! ', '? ', and newlines.

    Keeps punctuation attached to the sentence. Filters empties.
    """
    # Split on sentence-ending punctuation followed by space, or on newlines.
    # The regex captures the delimiter so we can re-attach punctuation.
    normalized = re.sub(r"\n{2,}", "\n", text)
    parts = re.split(r'(?<=[.!?])\s+|\n+', normalized)
    return [s.strip() for s in parts if s.strip()]


def _read_clipboard() -> str | None:
    """Read string contents from the macOS clipboard."""
    pb = NSPasteboard.generalPasteboard()
    content = pb.stringForType_(NSStringPboardType)
    return str(content) if content else None


def _write_clipboard(text: str | None) -> None:
    """Write string contents to the macOS clipboard."""
    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()
    if text is not None:
        pb.setString_forType_(text, NSStringPboardType)


def _clipboard_change_count() -> int:
    """Return the current macOS pasteboard change counter."""
    pb = NSPasteboard.generalPasteboard()
    return int(pb.changeCount())


def _simulate_cmd_c() -> None:
    """Simulate ⌘C keypress using Quartz CGEvents."""
    # keycode 8 = 'c' on US keyboard
    key_down = CGEventCreateKeyboardEvent(None, 8, True)
    key_up = CGEventCreateKeyboardEvent(None, 8, False)
    CGEventSetFlags(key_down, kCGEventFlagMaskCommand)
    CGEventSetFlags(key_up, kCGEventFlagMaskCommand)
    CGEventPost(kCGHIDEventTap, key_down)
    CGEventPost(kCGHIDEventTap, key_up)


def has_accessibility_permission() -> bool:
    """Return whether this process is trusted for Accessibility control."""
    try:
        return bool(AXIsProcessTrusted())
    except Exception:
        return False


def get_selected_text(copy_delay_s: float = 0.15, min_chars: int = 1) -> str | None:
    """Simulate ⌘C, read clipboard, restore previous clipboard contents.

    Returns the selected text, or None if nothing was selected.
    """
    # Save current clipboard
    original = _read_clipboard()
    before_count = _clipboard_change_count()

    # Simulate ⌘C
    _simulate_cmd_c()
    # Poll briefly for clipboard mutation from copy action.
    changed = False
    deadline = time.time() + copy_delay_s
    while time.time() < deadline:
        if _clipboard_change_count() != before_count:
            changed = True
            break
        time.sleep(0.01)

    # Read what was copied
    selected = _read_clipboard()

    # Restore original clipboard
    _write_clipboard(original)

    # If clipboard is empty/whitespace after ⌘C, nothing was selected.
    if not selected or not selected.strip():
        return None

    # No pasteboard change usually means there was no copyable selection.
    if not changed:
        return None

    cleaned = selected.strip()
    if len(cleaned) < min_chars:
        return None

    return cleaned
