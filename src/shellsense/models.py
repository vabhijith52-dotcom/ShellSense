"""ShellSense core domain models.

All models in this module are frozen and immutable where appropriate.
Separation of Intent, Plan, ApprovedPlan, and Result ensures strict adherence to
Security Invariants 5, 6, and 7.
"""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RiskLevel(StrEnum):
    """Fail-closed risk levels. Never use a permissive default or None."""
    SAFE = "SAFE"
    MODIFY = "MODIFY"
    DESTRUCTIVE = "DESTRUCTIVE"
    BLOCKED = "BLOCKED"


class Capability(StrEnum):
    """Closed enum of capability grants required for ShellSense operations."""
    SYSTEM_INFO_READ = "SYSTEM_INFO_READ"
    FILES_READ = "FILES_READ"
    FILES_MODIFY = "FILES_MODIFY"
    FILES_TRASH = "FILES_TRASH"
    PROCESS_TERMINATE = "PROCESS_TERMINATE"
    TASKS_BACKGROUND = "TASKS_BACKGROUND"


class ConfirmationKind(StrEnum):
    """Confirmation interaction kind for plans."""
    NONE = "none"
    BUTTON = "button"
    TOKEN = "token"


class ConfirmationHint(BaseModel):
    """Guidance for frontend confirmation input."""
    model_config = ConfigDict(frozen=True)

    kind: ConfirmationKind
    token: str | None = None
    prompt_message: str


class TargetFile(BaseModel):
    """Frozen representation of a filesystem target with metadata for TOCTOU checks."""
    model_config = ConfigDict(frozen=True)

    path: str
    exists: bool
    is_dir: bool = False
    size_bytes: int | None = None
    inode: int | None = None
    device: int | None = None
    mtime: float | None = None


class TargetProcess(BaseModel):
    """Frozen representation of an OS process target with PID and create_time."""
    model_config = ConfigDict(frozen=True)

    pid: int
    create_time: float
    name: str
    user: str
    cmdline: str
    cpu_percent: float = 0.0
    memory_rss_bytes: int = 0


class Intent(BaseModel):
    """Parsed user intent. Represents understanding only, with zero execution authority."""
    model_config = ConfigDict(frozen=True)

    operation: str
    params: dict[str, Any] = Field(default_factory=dict)
    confidence: float
    original_text: str


def compute_plan_hash(
    operation: str,
    target_files: tuple[TargetFile, ...],
    target_processes: tuple[TargetProcess, ...],
    parameters: dict[str, Any],
    risk_level: RiskLevel,
    summary: str,
    consequences: str,
    created_at: float,
    expires_at: float,
) -> str:
    """Compute deterministic SHA-256 hash over canonical plan fields."""
    canonical_payload = {
        "operation": operation,
        "target_files": [f.model_dump(mode="json") for f in target_files],
        "target_processes": [p.model_dump(mode="json") for p in target_processes],
        "parameters": parameters,
        "risk_level": risk_level.value,
        "summary": summary,
        "consequences": consequences,
        "created_at": created_at,
        "expires_at": expires_at,
    }
    canonical_bytes = json.dumps(
        canonical_payload, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(canonical_bytes).hexdigest()


class Plan(BaseModel):
    """Immutable, frozen plan binding exact resolved targets, parameters, and risk level."""
    model_config = ConfigDict(frozen=True)

    plan_id: str
    operation: str
    target_files: tuple[TargetFile, ...] = Field(default_factory=tuple)
    target_processes: tuple[TargetProcess, ...] = Field(default_factory=tuple)
    parameters: dict[str, Any] = Field(default_factory=dict)
    risk_level: RiskLevel
    summary: str
    consequences: str
    confirmation_hint: ConfirmationHint
    created_at: float
    expires_at: float
    plan_hash: str

    def verify_hash(self) -> bool:
        """Verify that the plan's hash matches its canonical content."""
        expected = compute_plan_hash(
            operation=self.operation,
            target_files=self.target_files,
            target_processes=self.target_processes,
            parameters=self.parameters,
            risk_level=self.risk_level,
            summary=self.summary,
            consequences=self.consequences,
            created_at=self.created_at,
            expires_at=self.expires_at,
        )
        return self.plan_hash == expected


class ApprovedPlan(BaseModel):
    """An approved plan.

    Invariants:
    - Can only be constructed by safety/approval.py via verify_and_approve_plan.
    - Carries an immutable snapshot of the original Plan and approval metadata.
    """
    model_config = ConfigDict(frozen=True)

    plan: Plan
    approved_at: float
    confirmation_input: str | None = None
    _sentinel: object = None

    def __init__(self, **data: Any) -> None:
        if data.pop("_sentinel", None) is not _APPROVED_PLAN_SENTINEL:
            raise PermissionError(
                "ApprovedPlan cannot be constructed directly. Use approval.approve_plan."
            )
        super().__init__(**data)


# Private sentinel to prevent unvetted construction of ApprovedPlan
_APPROVED_PLAN_SENTINEL = object()


class ExecutionStatus(StrEnum):
    """Status outcomes for plan execution."""
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    PARTIAL = "PARTIAL"


class TargetOutcome(BaseModel):
    """Outcome for a single target."""
    model_config = ConfigDict(frozen=True)

    target: str
    status: ExecutionStatus
    message: str


class Result(BaseModel):
    """Immutable execution outcome."""
    model_config = ConfigDict(frozen=True)

    status: ExecutionStatus
    outcomes: list[TargetOutcome] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    undo_record_id: str | None = None
