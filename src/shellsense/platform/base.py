"""Platform abstraction layer for ShellSense.

All OS-specific logic lives behind this abstraction to ensure operations never branch on OS.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from shellsense.models import TargetFile, TargetProcess


@dataclass(frozen=True)
class OSInfo:
    """Operating system metadata for display-only rendering."""
    system: str  # "Linux" | "Windows"
    release: str
    version: str
    machine: str
    display_name: str


class PlatformAdapter(ABC):
    """Abstract platform interface implemented by Linux and Windows adapters."""

    @abstractmethod
    def get_os_info(self) -> OSInfo:
        """Return platform details for read-only UI display."""
        ...

    @abstractmethod
    def is_root_or_admin(self) -> bool:
        """Check if ShellSense is running as root (Linux) or Administrator (Windows)."""
        ...

    @abstractmethod
    def get_hard_denied_paths(self) -> set[Path]:
        """Return operating-system hard-denied paths."""
        ...

    @abstractmethod
    def get_exact_only_denied_paths(self) -> set[Path]:
        """Return paths where only exact match is denied (e.g. root or user home root)."""
        ...

    @abstractmethod
    def is_reserved_or_invalid_path(self, path: Path) -> bool:
        """Check if path contains reserved OS device names, streams, or invalid prefixes."""
        ...

    @abstractmethod
    def get_protected_pids(self) -> set[int]:
        """Return set of PIDs that must never be terminated (PID 0, 1/4, self, parent)."""
        ...

    @abstractmethod
    def is_process_owned_by_current_user(self, pid: int) -> bool:
        """Check if the given PID is owned by the current user."""
        ...

    @abstractmethod
    def get_process_metadata(self, pid: int) -> TargetProcess | None:
        """Fetch current process metadata including PID and create_time for TOCTOU verification."""
        ...

    @abstractmethod
    def verify_target_file_unchanged(self, target: TargetFile) -> bool:
        """Verify that a target file has not changed since the plan was created."""
        ...

    @abstractmethod
    def verify_target_process_unchanged(self, target: TargetProcess) -> bool:
        """Verify that a target process PID has not been recycled."""
        ...

    @abstractmethod
    def move_to_trash(self, path: Path) -> None:
        """Move path to OS trash/recycle bin."""
        ...
