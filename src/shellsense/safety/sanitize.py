"""Text sanitization utilities for untrusted input.

Invariant 10: All text is untrusted (user input, filenames, process names, logs).
Strip control characters, ANSI escapes, and Unicode bidirectional override characters.
"""

from __future__ import annotations

import re

# ANSI escape sequence pattern
_ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

# Unicode bidirectional control characters (e.g. RLO U+202E, LRO U+202D, etc.)
_BIDI_OVERRIDES_RE = re.compile(r"[\u202A-\u202E\u2066-\u2069]")

# ASCII control characters (0x00 to 0x1F, except \t and \n), plus 0x7F (DEL)
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0B-\x1F\x7F]")


def sanitize_text(text: str | None) -> str:
    """Sanitize untrusted text for safe display and logging."""
    if not text:
        return ""

    # Strip ANSI escape sequences
    sanitized = _ANSI_ESCAPE_RE.sub("", text)

    # Strip Unicode bidirectional overrides
    sanitized = _BIDI_OVERRIDES_RE.sub("", sanitized)

    # Strip unprintable control characters
    sanitized = _CONTROL_CHARS_RE.sub("", sanitized)

    return sanitized
