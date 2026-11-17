"""Windows platform adapter for ShellSense."""

from __future__ import annotations

import contextlib
import getpass
import os
import platform
import re
from pathlib import Path

import platformdirs
import psutil
import send2trash

from shellsense.models import TargetFile, TargetProcess
from shellsense.platform.base import OSInfo, PlatformAdapter

_RESERVED_DOS_NAMES = frozenset({
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
})


class WindowsAdapter(PlatformAdapter):
    """Adapter for Windows systems (e.g. Windows 11)."""

    def get_os_info(self) -> OSInfo:
        return OSInfo(
            system="Windows",
            release=platform.release(),
            version=platform.version(),
            machine=platform.machine(),
            display_name=f"Windows {platform.release()} ({platform.machine()})",
        )

    def is_root_or_admin(self) -> bool:
        """ShellSense unconditionally refuses to run as Administrator."""
        try:
            import ctypes

            windll = getattr(ctypes, "windll", None)
            if windll is not None:
                return bool(windll.shell32.IsUserAnAdmin())
            return False
        except Exception:
            return False

    def get_hard_denied_paths(self) -> set[Path]:
        """Hard-coded Windows denial list per Section 8."""
        system_drive = os.environ.get("SYSTEMDRIVE", "C:")
        user_profile = Path(os.environ.get("USERPROFILE", Path.home())).resolve()
        denies = {
            Path(f"{system_drive}\\Windows").resolve(),
            Path(f"{system_drive}\\Program Files").resolve(),
            Path(f"{system_drive}\\Program Files (x86)").resolve(),
            Path(f"{system_drive}\\ProgramData").resolve(),
            user_profile,  # The user profile root directory itself
            Path(platformdirs.user_config_dir("shellsense", appauthor=False)).resolve(),
            Path(platformdirs.user_log_dir("shellsense", appauthor=False)).resolve(),
            Path(platformdirs.user_data_dir("shellsense", appauthor=False)).resolve(),
        }
        return denies

    def get_exact_only_denied_paths(self) -> set[Path]:
        """User profile root directory itself cannot be deleted/targeted,
        but granted folders inside (e.g. Downloads) are allowed.
        """
        user_profile = Path(os.environ.get("USERPROFILE", Path.home())).resolve()
        return {user_profile}

    def is_reserved_or_invalid_path(self, path: Path) -> bool:
        """Check for DOS devices, Alternate Data Streams, and UNC/extended prefixes."""
        path_str = str(path)

        # Reject UNC prefix and Win32 file namespace \\?\ or \??\
        if path_str.startswith(("\\\\", "//", "\\??\\", "//??//")):
            return True

        # Check for alternate data streams (colons beyond drive specifier e.g. C:)
        stripped_drive = re.sub(r"^[a-zA-Z]:", "", path_str)
        if ":" in stripped_drive:
            return True

        # Check for reserved DOS device names across all path components
        parts = re.split(r"[\\/]", path_str)
        for part in parts:
            if not part:
                continue
            stem = part.split(".")[0].upper()
            if stem in _RESERVED_DOS_NAMES:
                return True

        return False

    def get_protected_pids(self) -> set[int]:
        protected = {0, 4}  # System Idle and System on Windows
        with contextlib.suppress(Exception):
            protected.add(os.getpid())
            protected.add(os.getppid())
        return protected

    def is_process_owned_by_current_user(self, pid: int) -> bool:
        try:
            proc = psutil.Process(pid)
            proc_username = proc.username()
            # Windows usernames often come as DOMAIN\User
            current_user = getpass.getuser().lower()
            return proc_username.lower().endswith(current_user)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    def get_process_metadata(self, pid: int) -> TargetProcess | None:
        try:
            proc = psutil.Process(pid)
            with proc.oneshot():
                return TargetProcess(
                    pid=proc.pid,
                    create_time=proc.create_time(),
                    name=proc.name(),
                    user=proc.username(),
                    cmdline=" ".join(proc.cmdline()[:10]),
                    cpu_percent=proc.cpu_percent(interval=None),
                    memory_rss_bytes=proc.memory_info().rss,
                )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None

    def verify_target_file_unchanged(self, target: TargetFile) -> bool:
        target_path = Path(target.path)
        if not target_path.exists():
            return not target.exists

        try:
            st = target_path.stat()
            if target.size_bytes is not None and st.st_size != target.size_bytes:
                return False
            if target.mtime is not None:
                return abs(st.st_mtime - target.mtime) <= 0.001
            return True
        except (OSError, PermissionError):
            return False

    def verify_target_process_unchanged(self, target: TargetProcess) -> bool:
        try:
            proc = psutil.Process(target.pid)
            return abs(proc.create_time() - target.create_time) < 0.01
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    def move_to_trash(self, path: Path) -> None:
        send2trash.send2trash(str(path))
