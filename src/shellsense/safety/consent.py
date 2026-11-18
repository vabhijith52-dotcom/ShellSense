"""Consent management and capability gate for ShellSense.

Invariant 11: Locked by default. Zero system access until granted.
Invariant 12: Consent lives outside the repo, per user and per machine.
Invariant 13: Grants require a live human (interactive TTY or GUI wizard).
"""

from __future__ import annotations

import getpass
import hashlib
import json
import os
import stat
import sys
import time
import uuid
from pathlib import Path

import platformdirs
from pydantic import BaseModel, ConfigDict, Field

from shellsense.models import Capability


class ConsentRecord(BaseModel):
    """Schema for persistent consent.json outside the repository."""
    model_config = ConfigDict(frozen=True)

    os_platform: str
    username: str
    machine_id_hash: str
    major_version: str
    capabilities: list[Capability]
    folder_roots: list[str] = Field(default_factory=list)
    manifest_hash: str
    created_at: float
    expires_at: float | None = None


def get_machine_id_hash() -> str:
    """Generate deterministic SHA-256 hash of local machine identifier."""
    node_id = str(uuid.getnode()).encode("utf-8")
    return hashlib.sha256(node_id).hexdigest()


def compute_manifest_hash(
    os_platform: str,
    username: str,
    machine_id_hash: str,
    major_version: str,
    capabilities: list[Capability],
    folder_roots: list[str],
) -> str:
    """Compute integrity hash for granted consent capabilities."""
    sorted_caps = sorted([c.value for c in capabilities])
    sorted_roots = sorted([str(Path(r).expanduser().resolve()) for r in folder_roots])
    payload = {
        "os_platform": os_platform,
        "username": username,
        "machine_id_hash": machine_id_hash,
        "major_version": major_version,
        "capabilities": sorted_caps,
        "folder_roots": sorted_roots,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def get_repo_root() -> Path | None:
    """Find the root directory of the ShellSense repository if running from source."""
    try:
        current = Path(__file__).resolve()
        for p in current.parents:
            if (p / "pyproject.toml").exists() and ((p / "src" / "shellsense").exists() or (p / ".git").exists()):
                return p
    except Exception:
        pass
    return None


def is_inside_repo(path: Path, repo_root: Path | None = None) -> bool:
    """Check if a path is located inside the application's own repository root.

    Invariant 12: Consent lives outside the repo, per user and per machine,
    and is never shipped or loaded from inside the application repository.
    """
    target_root = repo_root or get_repo_root()
    if target_root is None:
        return False

    try:
        c = path.resolve()
        p = target_root.resolve()

        # Case-insensitive comparison on Windows
        if os.name == "nt" or sys.platform == "win32":
            c_parts = [part.lower() for part in c.parts]
            p_parts = [part.lower() for part in p.parts]
            return len(c_parts) >= len(p_parts) and c_parts[:len(p_parts)] == p_parts

        c.relative_to(p)
        return True
    except (ValueError, Exception):
        return False


def is_inside_git_repo(path: Path, repo_root: Path | None = None) -> bool:
    """Check whether a path is located inside the ShellSense repository root.

    Maintained for backwards-compatibility; checks whether path is a subpath of
    the application's own repository root rather than blanket-blocking any path
    that happens to have a .git folder in its parent tree.
    """
    return is_inside_repo(path, repo_root=repo_root)


class PermissionGate:
    """Gatekeeper enforcing locked-by-default capability access."""

    def __init__(self, config_dir: Path | None = None, repo_root: Path | None = None) -> None:
        default_dir = platformdirs.user_config_dir("shellsense", appauthor=False)
        self.config_dir = config_dir or Path(default_dir)
        self.consent_file = self.config_dir / "consent.json"
        self.repo_root = repo_root or get_repo_root()
        self._cached_grant: ConsentRecord | None = None
        self._last_loaded: float = 0.0

    def is_locked(self) -> bool:
        """Returns True if no valid grant exists, keeping the entire system locked."""
        grant = self.get_current_grant()
        return grant is None

    def get_current_grant(self) -> ConsentRecord | None:
        """Load and strictly validate the current consent grant."""
        if not self.consent_file.exists():
            return None

        # Invariant 12: Reject consent file if inside the ShellSense repository
        if is_inside_repo(self.consent_file, repo_root=self.repo_root):
            return None

        try:
            # Check owner-only permissions on POSIX systems
            if os.name == "posix":
                st = self.consent_file.stat()
                if bool(st.st_mode & (stat.S_IRWXG | stat.S_IRWXO)):
                    # File has group or other permissions: reject for security
                    return None

            data = json.loads(self.consent_file.read_text(encoding="utf-8"))
            record = ConsentRecord(**data)

            # Validate machine binding, user binding, and platform
            if record.os_platform != sys.platform:
                return None
            if record.username != getpass.getuser():
                return None
            if record.machine_id_hash != get_machine_id_hash():
                return None

            # Validate expiry
            if record.expires_at is not None and time.time() > record.expires_at:
                return None

            # Validate manifest integrity
            expected_hash = compute_manifest_hash(
                os_platform=record.os_platform,
                username=record.username,
                machine_id_hash=record.machine_id_hash,
                major_version=record.major_version,
                capabilities=record.capabilities,
                folder_roots=record.folder_roots,
            )
            if record.manifest_hash != expected_hash:
                return None

            return record

        except Exception:
            # Fail closed on any parsing or validation error
            return None

    def has_capability(self, capability: Capability) -> bool:
        """Check if a specific capability is granted in the current valid grant."""
        grant = self.get_current_grant()
        if grant is None:
            return False
        return capability in grant.capabilities

    def get_granted_roots(self) -> list[Path]:
        """Return the resolved list of allowed roots granted by the user."""
        grant = self.get_current_grant()
        if grant is None:
            return []
        return [Path(r).expanduser().resolve() for r in grant.folder_roots]

    def write_grant(
        self,
        capabilities: list[Capability],
        folder_roots: list[str],
        expires_at: float | None = None,
        force_tty_check: bool = True,
    ) -> bool:
        """Persist a new consent grant with owner-only permissions.

        Invariant 13: Grants require a live human.
        """
        if force_tty_check and not (sys.stdin.isatty() and sys.stdout.isatty()):
            raise PermissionError(
                "Interactive TTY required to grant permissions without GUI wizard."
            )

        # Invariant 12: Ensure config dir is not inside the ShellSense repository
        if is_inside_repo(self.consent_file, repo_root=self.repo_root):
            raise PermissionError("Consent file cannot be located within the ShellSense repository.")

        self.config_dir.mkdir(parents=True, exist_ok=True)
        # Enforce owner-only directory permissions on POSIX
        if os.name == "posix":
            self.config_dir.chmod(0o700)

        os_platform = sys.platform
        username = getpass.getuser()
        machine_hash = get_machine_id_hash()
        major_ver = "0"

        manifest_hash = compute_manifest_hash(
            os_platform=os_platform,
            username=username,
            machine_id_hash=machine_hash,
            major_version=major_ver,
            capabilities=capabilities,
            folder_roots=folder_roots,
        )

        record = ConsentRecord(
            os_platform=os_platform,
            username=username,
            machine_id_hash=machine_hash,
            major_version=major_ver,
            capabilities=capabilities,
            folder_roots=folder_roots,
            manifest_hash=manifest_hash,
            created_at=time.time(),
            expires_at=expires_at,
        )

        temp_file = self.consent_file.with_suffix(".tmp")
        temp_file.write_text(record.model_dump_json(indent=2), encoding="utf-8")
        if os.name == "posix":
            temp_file.chmod(0o600)
        temp_file.replace(self.consent_file)
        if os.name == "posix":
            self.consent_file.chmod(0o600)

        return True

    def revoke(self) -> bool:
        """Immediately revoke all capabilities by deleting consent.json."""
        if self.consent_file.exists():
            self.consent_file.unlink()
            return True
        return False
