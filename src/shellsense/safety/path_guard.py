"""Filesystem path validation and traversal guard for ShellSense.

Enforces Section 8 path safety, hard-coded OS denials, and symlink protection.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from shellsense.platform import get_platform_adapter


class PathGuard:
    """Validates filesystem paths against allowed roots, hard denials, and escape attempts."""

    def __init__(self, platform_adapter: Any = None) -> None:
        self.adapter = platform_adapter or get_platform_adapter()

    def validate_path(
        self,
        candidate_path: str | Path,
        allowed_roots: list[Path],
        settings_denies: list[Path] | None = None,
    ) -> tuple[bool, str]:
        """Validate whether a candidate path is safe and permitted.

        Returns (is_safe, refusal_reason).
        Fail closed on any exception or boundary violation.
        """
        try:
            raw_str = str(candidate_path).strip()
            if not raw_str:
                return False, "Path is empty."

            # Refuse wildcards that target entire directories
            if raw_str in {"*", ".*", "/*", "\\*", "**"}:
                return False, "Whole-directory wildcards are refused."

            candidate = Path(raw_str)

            # Check platform-specific reserved names, streams, UNC
            if self.adapter.is_reserved_or_invalid_path(candidate):
                return False, "Path contains invalid, reserved, or UNC device syntax."

            # Check for symlink on the candidate: operate on link itself, never follow outside
            if candidate.is_symlink():
                target = candidate.readlink()
                if not Path(target).is_absolute():
                    target = (candidate.parent / target).resolve()
                else:
                    target = Path(target).resolve()

            # Resolve candidate path completely
            resolved = candidate.expanduser().resolve()

            # 1. Check against hard-coded OS deny list
            # Note: For root filesystem and user home root itself, exact match is denied,
            # but subpaths are permitted if they fall under explicitly granted roots.
            # For system folders (/etc, /boot, /bin, C:\Windows, ~/.ssh), subpaths are forbidden.
            hard_denies = self.adapter.get_hard_denied_paths()
            exact_only_denies = self.adapter.get_exact_only_denied_paths()

            for denied in hard_denies:
                try:
                    if resolved == denied:
                        return False, f"Access to system-protected path '{denied}' is forbidden."
                    if denied not in exact_only_denies and self._is_subpath(resolved, denied):
                        return False, f"Access to system-protected path '{denied}' is forbidden."
                except Exception:
                    return False, "Path resolution error against system deny list."

            # 2. Check against settings-configured denied paths
            if settings_denies:
                for denied in settings_denies:
                    denied_resolved = Path(denied).expanduser().resolve()
                    if resolved == denied_resolved or self._is_subpath(resolved, denied_resolved):
                        return (
                            False,
                            f"Access to configured denied path '{denied_resolved}' is forbidden.",
                        )

            # 3. Check allowed roots: path must fall strictly inside at least one granted root
            if not allowed_roots:
                return False, "No allowed roots granted. ShellSense is locked."

            inside_allowed = False
            for root in allowed_roots:
                root_resolved = Path(root).expanduser().resolve()
                if resolved == root_resolved or self._is_subpath(resolved, root_resolved):
                    inside_allowed = True
                    break

            if not inside_allowed:
                return False, f"Path '{resolved}' is outside granted folder roots."

            return True, "Path is safe and permitted."

        except Exception as e:
            # Invariant 1: Fail closed on any exception
            return False, f"Path evaluation failed: {e}"

    @staticmethod
    def _is_subpath(target: Path, parent: Path) -> bool:
        """Check if target is a subpath of parent (case-insensitive on Windows)."""
        try:
            target_parts = [p.lower() if os.name == "nt" else p for p in target.parts]
            parent_parts = [p.lower() if os.name == "nt" else p for p in parent.parts]

            if len(target_parts) <= len(parent_parts):
                return False

            return target_parts[: len(parent_parts)] == parent_parts
        except Exception:
            return False
