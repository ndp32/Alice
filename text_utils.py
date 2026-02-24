"""Text processing and clipboard operations for Kokoro Reader."""

import re
import time

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
    parts = re.split(r'(?<=[.!?])\s+|\n+', text)
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


def _simulate_cmd_c() -> None:
    """Simulate ⌘C keypress using Quartz CGEvents."""
    # keycode 8 = 'c' on US keyboard
    key_down = CGEventCreateKeyboardEvent(None, 8, True)
    key_up = CGEventCreateKeyboardEvent(None, 8, False)
    CGEventSetFlags(key_down, kCGEventFlagMaskCommand)
    CGEventSetFlags(key_up, kCGEventFlagMaskCommand)
    CGEventPost(kCGHIDEventTap, key_down)
    CGEventPost(kCGHIDEventTap, key_up)


def get_selected_text() -> str | None:
    """Simulate ⌘C, read clipboard, restore previous clipboard contents.

    Returns the selected text, or None if nothing was selected.
    """
    # Save current clipboard
    original = _read_clipboard()

    # Clear clipboard so we can detect if ⌘C actually copied something
    _write_clipboard(None)

    # Simulate ⌘C
    _simulate_cmd_c()
    time.sleep(0.15)  # wait for copy to complete

    # Read what was copied
    selected = _read_clipboard()

    # Restore original clipboard
    _write_clipboard(original)

    # If clipboard is still empty after ⌘C, nothing was selected
    if not selected:
        return None

    return selected
