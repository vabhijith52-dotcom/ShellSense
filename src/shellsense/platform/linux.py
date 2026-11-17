"""Linux platform adapter for ShellSense."""

from __future__ import annotations

import getpass
import os
import platform
from pathlib import Path

import platformdirs
import psutil
import send2trash

from shellsense.models import TargetFile, TargetProcess
from shellsense.platform.base import OSInfo, PlatformAdapter


class LinuxAdapter(PlatformAdapter):
    """Adapter for Linux systems (e.g. Ubuntu 24.04)."""

    def get_os_info(self) -> OSInfo:
        return OSInfo(
            system="Linux",
            release=platform.release(),
            version=platform.version(),
            machine=platform.machine(),
            display_name=f"Linux {platform.release()} ({platform.machine()})",
        )

    def is_root_or_admin(self) -> bool:
        """ShellSense unconditionally refuses to run as root."""
        return os.geteuid() == 0

    def get_hard_denied_paths(self) -> set[Path]:
        """Hard-coded Linux denial list per Section 8."""
        home = Path.home().resolve()
        denies = {
            Path("/").resolve(),
            Path("/boot").resolve(),
            Path("/etc").resolve(),
            Path("/usr").resolve(),
            Path("/bin").resolve(),
            Path("/sbin").resolve(),
            Path("/var").resolve(),
            Path("/proc").resolve(),
            Path("/sys").resolve(),
            Path("/dev").resolve(),
            home,  # The home directory itself
            (home / ".ssh").resolve(),
            (home / ".gnupg").resolve(),
            Path(platformdirs.user_config_dir("shellsense", appauthor=False)).resolve(),
            Path(platformdirs.user_log_dir("shellsense", appauthor=False)).resolve(),
            Path(platformdirs.user_data_dir("shellsense", appauthor=False)).resolve(),
        }
        # Add dynamic /lib* paths
        for p in Path("/").glob("lib*"):
            denies.add(p.resolve())
        return denies

    def get_exact_only_denied_paths(self) -> set[Path]:
        """Root filesystem '/' and user home root cannot be targeted directly,
        but granted folders inside home (e.g. ~/Downloads) are allowed.
        """
        return {Path("/").resolve(), Path.home().resolve()}

    def is_reserved_or_invalid_path(self, path: Path) -> bool:
        """Linux paths do not have DOS devices, but reject null bytes and control chars."""
        return "\0" in str(path)

    def get_protected_pids(self) -> set[int]:
        protected = {0, 1, os.getpid(), os.getppid()}
        return protected

    def is_process_owned_by_current_user(self, pid: int) -> bool:
        try:
            proc = psutil.Process(pid)
            proc_username = proc.username()
            return proc_username == getpass.getuser()
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
            if target.inode is not None and st.st_ino != target.inode:
                return False
            if target.device is not None and st.st_dev != target.device:
                return False
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
