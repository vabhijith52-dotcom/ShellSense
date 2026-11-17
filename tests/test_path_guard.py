"""Tests for path safety, boundary validation, and traversal guards."""

from pathlib import Path

from shellsense.platform.linux import LinuxAdapter
from shellsense.platform.windows import WindowsAdapter
from shellsense.safety.path_guard import PathGuard


def test_path_outside_allowed_roots_rejected(tmp_path: Path) -> None:
    allowed_root = tmp_path / "sandbox"
    allowed_root.mkdir()
    outside_file = tmp_path / "other" / "secret.txt"

    guard = PathGuard()
    safe, reason = guard.validate_path(outside_file, allowed_roots=[allowed_root])
    assert safe is False
    assert "outside granted folder roots" in reason


def test_path_inside_allowed_root_permitted(tmp_path: Path) -> None:
    allowed_root = tmp_path / "sandbox"
    allowed_root.mkdir()
    valid_file = allowed_root / "document.txt"

    guard = PathGuard()
    safe, reason = guard.validate_path(valid_file, allowed_roots=[allowed_root])
    assert safe is True


def test_path_traversal_escape_rejected(tmp_path: Path) -> None:
    allowed_root = tmp_path / "sandbox"
    allowed_root.mkdir()
    traversal_path = allowed_root / ".." / "secret.txt"

    guard = PathGuard()
    safe, reason = guard.validate_path(traversal_path, allowed_roots=[allowed_root])
    assert safe is False


def test_whole_directory_wildcard_rejected(tmp_path: Path) -> None:
    guard = PathGuard()
    safe, reason = guard.validate_path("*", allowed_roots=[tmp_path])
    assert safe is False
    assert "Whole-directory wildcards are refused" in reason


def test_linux_hard_denied_paths() -> None:
    guard = PathGuard(platform_adapter=LinuxAdapter())
    safe, reason = guard.validate_path("/etc/passwd", allowed_roots=[Path("/")])
    assert safe is False
    assert "system-protected path" in reason


def test_windows_reserved_names() -> None:
    guard = PathGuard(platform_adapter=WindowsAdapter())
    safe, reason = guard.validate_path("C:\\sandbox\\CON.txt", allowed_roots=[Path("C:\\sandbox")])
    assert safe is False
    assert "reserved" in reason


def test_windows_alternate_data_stream() -> None:
    guard = PathGuard(platform_adapter=WindowsAdapter())
    safe, reason = guard.validate_path(
        "C:\\sandbox\\file.txt:hidden", allowed_roots=[Path("C:\\sandbox")]
    )
    assert safe is False
    assert "invalid, reserved, or UNC" in reason


def test_windows_unc_path_rejected() -> None:
    guard = PathGuard(platform_adapter=WindowsAdapter())
    safe, _ = guard.validate_path(
        "\\\\evil-server\\share\\file.txt", allowed_roots=[Path("C:\\sandbox")]
    )
    assert safe is False
