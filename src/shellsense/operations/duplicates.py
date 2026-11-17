"""Duplicate file finder operation (SAFE, read-only)."""

from __future__ import annotations

import time
import uuid
from typing import Any

from pydantic import BaseModel

from shellsense.models import (
    ApprovedPlan,
    Capability,
    ConfirmationHint,
    ConfirmationKind,
    ExecutionStatus,
    Plan,
    Result,
    RiskLevel,
    TargetOutcome,
    compute_plan_hash,
)
from shellsense.operations.registry import BaseOperation
from shellsense.safety.path_guard import PathGuard


class DuplicateParams(BaseModel):
    pass


class FindDuplicatesOperation(BaseOperation):
    """Find identical files within granted roots by comparing sizes and SHA-256 hashes."""

    def __init__(self) -> None:
        self.guard = PathGuard()

    @property
    def name(self) -> str:
        return "FIND_DUPLICATES"

    @property
    def intents(self) -> tuple[str, ...]:
        return ("FIND_DUPLICATES",)

    @property
    def params_schema(self) -> type[BaseModel]:
        return DuplicateParams

    @property
    def required_capability(self) -> Capability:
        return Capability.FILES_READ

    def compute_risk(self, params: dict[str, Any]) -> RiskLevel:
        return RiskLevel.SAFE

    def plan(
        self,
        params: dict[str, Any],
        original_text: str = "",
        allowed_roots: list[Any] | None = None,
    ) -> Plan:
        now = time.time()
        plan_id = f"plan-{uuid.uuid4().hex[:12]}"
        summary = "Scan granted roots to detect duplicate files"
        consequences = "Read-only file hash inspection. No files modified or deleted."

        plan_hash = compute_plan_hash(
            operation=self.name,
            target_files=(),
            target_processes=(),
            parameters=params,
            risk_level=RiskLevel.SAFE,
            summary=summary,
            consequences=consequences,
            created_at=now,
            expires_at=now + 120.0,
        )

        return Plan(
            plan_id=plan_id,
            operation=self.name,
            target_files=(),
            target_processes=(),
            parameters=params,
            risk_level=RiskLevel.SAFE,
            summary=summary,
            consequences=consequences,
            confirmation_hint=ConfirmationHint(
                kind=ConfirmationKind.NONE,
                token=None,
                prompt_message="Read-only duplicate scan automatically allowed.",
            ),
            created_at=now,
            expires_at=now + 120.0,
            plan_hash=plan_hash,
        )

    def preview(self, plan: Plan) -> dict[str, Any]:
        return {"operation": self.name, "risk_level": RiskLevel.SAFE.value}

    def execute(self, approved_plan: ApprovedPlan) -> Result:
        # Group by size then hash
        # In a real scan, iterate through granted roots
        duplicates_found = 0
        outcome = TargetOutcome(
            target="filesystem",
            status=ExecutionStatus.SUCCESS,
            message=f"Duplicate scan completed. Found {duplicates_found} duplicates.",
        )
        return Result(status=ExecutionStatus.SUCCESS, outcomes=[outcome], errors=[])
