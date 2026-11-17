"""Audit logging system for ShellSense.

Invariant 8: Every decision is audit-logged (auto-allowed, approved, denied, refused, failed).
Invariant 13 & Section 13: Append-only JSON Lines, owner-only permissions, rotated by size,
hash-chained. An audit write failure on a non-SAFE operation aborts the operation.
"""

from __future__ import annotations

import hashlib
import os
import threading
import time
from enum import StrEnum
from pathlib import Path

import platformdirs
from pydantic import BaseModel, ConfigDict

from shellsense.models import RiskLevel
from shellsense.safety.sanitize import sanitize_text


class AuditDecision(StrEnum):
    """Decision outcomes recorded in audit log."""
    AUTO_ALLOWED = "AUTO_ALLOWED"
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    REFUSED = "REFUSED"
    FAILED = "FAILED"


class AuditRecord(BaseModel):
    """Immutable audit entry."""
    model_config = ConfigDict(frozen=True)

    timestamp: float
    session_id: str
    original_text: str
    intent: str
    plan_hash: str | None
    risk: str
    decision: AuditDecision
    result_status: str | None = None
    errors: list[str] = []
    prev_hash: str


class AuditLogger:
    """Thread-safe append-only audit logger."""

    def __init__(
        self,
        log_dir: Path | None = None,
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 5,
    ) -> None:
        default_dir = platformdirs.user_log_dir("shellsense", appauthor=False)
        self.log_dir = log_dir or Path(default_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        if os.name == "posix":
            self.log_dir.chmod(0o700)

        self.log_file = self.log_dir / "audit.jsonl"
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self._lock = threading.Lock()
        self._last_hash = self._recover_last_hash()

    def _recover_last_hash(self) -> str:
        """Read the last record's hash to maintain hash-chaining."""
        if not self.log_file.exists():
            return "0" * 64

        try:
            with open(self.log_file, encoding="utf-8") as f:
                lines = f.readlines()
                if lines:
                    last_line = lines[-1].strip()
                    if last_line:
                        return hashlib.sha256(last_line.encode("utf-8")).hexdigest()
        except Exception:
            pass
        return "0" * 64

    def _rotate_if_needed(self) -> None:
        """Rotate audit log if exceeding max bytes."""
        if not self.log_file.exists():
            return

        try:
            if self.log_file.stat().st_size >= self.max_bytes:
                for i in range(self.backup_count - 1, 0, -1):
                    src = self.log_dir / f"audit.jsonl.{i}"
                    dest = self.log_dir / f"audit.jsonl.{i + 1}"
                    if src.exists():
                        src.replace(dest)

                first_backup = self.log_dir / "audit.jsonl.1"
                self.log_file.replace(first_backup)
                self._last_hash = "0" * 64
        except Exception:
            pass

    def log(
        self,
        session_id: str,
        original_text: str,
        intent: str,
        plan_hash: str | None,
        risk: RiskLevel,
        decision: AuditDecision,
        result_status: str | None = None,
        errors: list[str] | None = None,
    ) -> None:
        """Record an audit decision.

        Fail closed: An audit write failure on a non-SAFE operation raises an exception
        to abort the operation.
        """
        record = AuditRecord(
            timestamp=time.time(),
            session_id=sanitize_text(session_id),
            original_text=sanitize_text(original_text),
            intent=sanitize_text(intent),
            plan_hash=plan_hash,
            risk=risk.value,
            decision=decision,
            result_status=result_status,
            errors=[sanitize_text(e) for e in (errors or [])],
            prev_hash=self._last_hash,
        )

        serialized = record.model_dump_json() + "\n"
        serialized_bytes = serialized.encode("utf-8")
        entry_hash = hashlib.sha256(serialized_bytes).hexdigest()

        try:
            with self._lock:
                self._rotate_if_needed()
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(serialized)
                if os.name == "posix":
                    self.log_file.chmod(0o600)
                self._last_hash = entry_hash
        except Exception as exc:
            # Section 13: An audit write failure on a non-SAFE operation aborts the operation.
            if risk != RiskLevel.SAFE:
                raise RuntimeError(f"Audit log write failed for non-SAFE operation: {exc}") from exc


DEFAULT_AUDIT_LOGGER = AuditLogger()
