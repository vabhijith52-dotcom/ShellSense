"""Tests for platform adapters and privilege checks."""

from shellsense.platform import get_platform_adapter
from shellsense.platform.linux import LinuxAdapter
from shellsense.platform.windows import WindowsAdapter


def test_platform_adapter_detection() -> None:
    adapter = get_platform_adapter()
    info = adapter.get_os_info()
    assert info.system in {"Linux", "Windows"}
    assert len(info.display_name) > 0


def test_linux_adapter_protected_pids() -> None:
    linux = LinuxAdapter()
    protected = linux.get_protected_pids()
    assert 0 in protected
    assert 1 in protected


def test_windows_adapter_protected_pids() -> None:
    windows = WindowsAdapter()
    protected = windows.get_protected_pids()
    assert 0 in protected
    assert 4 in protected
