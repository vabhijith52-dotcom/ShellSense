"""Tests for consent records, locked-by-default behavior, and grant verification."""

from pathlib import Path

import pytest

from shellsense.models import Capability
from shellsense.safety.consent import (
    PermissionGate,
    is_inside_repo,
)


def test_locked_by_default(tmp_path: Path) -> None:
    # A fresh directory with no consent.json is locked
    gate = PermissionGate(config_dir=tmp_path)
    assert gate.is_locked() is True
    assert gate.has_capability(Capability.SYSTEM_INFO_READ) is False
    assert gate.get_granted_roots() == []


def test_grant_write_and_read(tmp_path: Path) -> None:
    gate = PermissionGate(config_dir=tmp_path)
    root_folder = tmp_path / "documents"
    root_folder.mkdir()

    # Write grant with force_tty_check=False for non-interactive test
    gate.write_grant(
        capabilities=[Capability.SYSTEM_INFO_READ, Capability.FILES_READ],
        folder_roots=[str(root_folder)],
        force_tty_check=False,
    )

    assert gate.is_locked() is False
    assert gate.has_capability(Capability.SYSTEM_INFO_READ) is True
    assert gate.has_capability(Capability.FILES_READ) is True
    assert gate.has_capability(Capability.FILES_MODIFY) is False
    assert root_folder.resolve() in gate.get_granted_roots()


def test_consent_inside_git_repo_rejected(tmp_path: Path) -> None:
    # Simulate the ShellSense repository
    fake_git_dir = tmp_path / "repo"
    (fake_git_dir / ".git").mkdir(parents=True)
    fake_config = fake_git_dir / "config"
    fake_config.mkdir()

    gate = PermissionGate(config_dir=fake_config, repo_root=fake_git_dir)
    # Attempting to write or read consent from inside the repository must fail
    with pytest.raises(PermissionError, match="repository"):
        gate.write_grant([Capability.SYSTEM_INFO_READ], [], force_tty_check=False)

    # Reading from inside repository must also return None / locked
    assert is_inside_repo(fake_config / "consent.json", repo_root=fake_git_dir) is True


def test_ancestor_git_folder_outside_repo_permitted(tmp_path: Path) -> None:
    # Scenario: Developer PC has .git in home or ancestor directory (e.g. C:\Users\user\.git)
    # but the ShellSense repository is cloned elsewhere (e.g. E:\AA\ShellSense).
    user_home = tmp_path / "user_home"
    (user_home / ".git").mkdir(parents=True)
    config_dir = user_home / "AppData" / "Local" / "shellsense"
    config_dir.mkdir(parents=True)

    repo_dir = tmp_path / "drives" / "E" / "AA" / "ShellSense"
    repo_dir.mkdir(parents=True)

    gate = PermissionGate(config_dir=config_dir, repo_root=repo_dir)
    assert is_inside_repo(config_dir / "consent.json", repo_root=repo_dir) is False

    # This MUST succeed and not be blanket-blocked!
    written = gate.write_grant([Capability.SYSTEM_INFO_READ], [], force_tty_check=False)
    assert written is True
    assert gate.is_locked() is False
    assert gate.has_capability(Capability.SYSTEM_INFO_READ) is True


def test_revocation_locks_system(tmp_path: Path) -> None:
    gate = PermissionGate(config_dir=tmp_path)
    gate.write_grant([Capability.SYSTEM_INFO_READ], [], force_tty_check=False)
    assert gate.is_locked() is False

    revoked = gate.revoke()
    assert revoked is True
    assert gate.is_locked() is True


def test_non_tty_grant_rejected(tmp_path: Path) -> None:
    gate = PermissionGate(config_dir=tmp_path)
    # With force_tty_check=True (the default), non-TTY pytest execution must be rejected
    with pytest.raises(PermissionError, match="Interactive TTY required"):
        gate.write_grant([Capability.SYSTEM_INFO_READ], [], force_tty_check=True)
