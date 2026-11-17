"""Archive operations (create zip backup archive)."""

from __future__ import annotations

import os
import time
import uuid
import zipfile
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from shellsense.models import (
    ApprovedPlan,
    Capability,
    ConfirmationHint,
    ConfirmationKind,
    ExecutionStatus,
    Plan,
    Result,
    RiskLevel,
    TargetFile,
    TargetOutcome,
    compute_plan_hash,
)
from shellsense.operations.registry import BaseOperation
from shellsense.safety.path_guard import PathGuard


class ArchiveParams(BaseModel):
    target: str = Field(default="")
    dest: str | None = None


class CreateArchiveOperation(BaseOperation):
    """Create a zip archive of a permitted target (MODIFY)."""

    def __init__(self) -> None:
        self.guard = PathGuard()

    @property
    def name(self) -> str:
        return "CREATE_ARCHIVE"

    @property
    def intents(self) -> tuple[str, ...]:
        return ("CREATE_ARCHIVE",)

    @property
    def params_schema(self) -> type[BaseModel]:
        return ArchiveParams

    @property
    def required_capability(self) -> Capability:
        return Capability.FILES_MODIFY

    def compute_risk(self, params: dict[str, Any]) -> RiskLevel:
        return RiskLevel.MODIFY

    def plan(
        self,
        params: dict[str, Any],
        original_text: str = "",
        allowed_roots: list[Any] | None = None,
    ) -> Plan:
        roots = [Path(r) for r in (allowed_roots or [])]
        raw_target = params.get("target") or (str(roots[0]) if roots else "")
        target_path = Path(raw_target).expanduser().resolve()

        safe, reason = self.guard.validate_path(target_path, allowed_roots=roots)
        if not safe:
            raise PermissionError(f"Target '{target_path}' is not permitted: {reason}")
        if not target_path.exists():
            raise FileNotFoundError(f"Target '{target_path}' does not exist.")

        dest_path = Path(params.get("dest") or f"{target_path}.zip").expanduser().resolve()
        safe_dest, reason_dest = self.guard.validate_path(dest_path, allowed_roots=roots)
        if not safe_dest:
            raise PermissionError(f"Destination '{dest_path}' is not permitted: {reason_dest}")

        st = target_path.stat()
        target = TargetFile(
            path=str(target_path),
            exists=True,
            is_dir=target_path.is_dir(),
            size_bytes=st.st_size if not target_path.is_dir() else None,
            inode=st.st_ino,
            device=st.st_dev,
            mtime=st.st_mtime,
        )

        now = time.time()
        plan_id = f"plan-{uuid.uuid4().hex[:12]}"
        summary = f"Create backup archive of '{target_path.name}' at '{dest_path.name}'"
        consequences = f"Will compress target into '{dest_path}'."

        plan_hash = compute_plan_hash(
            operation=self.name,
            target_files=(target,),
            target_processes=(),
            parameters={"target": str(target_path), "dest": str(dest_path)},
            risk_level=RiskLevel.MODIFY,
            summary=summary,
            consequences=consequences,
            created_at=now,
            expires_at=now + 120.0,
        )

        return Plan(
            plan_id=plan_id,
            operation=self.name,
            target_files=(target,),
            target_processes=(),
            parameters={"target": str(target_path), "dest": str(dest_path)},
            risk_level=RiskLevel.MODIFY,
            summary=summary,
            consequences=consequences,
            confirmation_hint=ConfirmationHint(
                kind=ConfirmationKind.BUTTON,
                token=None,
                prompt_message="Click approve to create archive.",
            ),
            created_at=now,
            expires_at=now + 120.0,
            plan_hash=plan_hash,
        )

    def preview(self, plan: Plan) -> dict[str, Any]:
        return {
            "operation": self.name,
            "target": plan.parameters.get("target"),
            "dest": plan.parameters.get("dest"),
            "risk_level": RiskLevel.MODIFY.value,
        }

    def execute(self, approved_plan: ApprovedPlan) -> Result:
        target_path = Path(approved_plan.plan.parameters["target"])
        dest_path = Path(approved_plan.plan.parameters["dest"])

        try:
            with zipfile.ZipFile(dest_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                if target_path.is_dir():
                    for root, _, files in os.walk(target_path):
                        for file in files:
                            full_path = Path(root) / file
                            zipf.write(full_path, full_path.relative_to(target_path))
                else:
                    zipf.write(target_path, target_path.name)

            outcome = TargetOutcome(
                target=str(dest_path),
                status=ExecutionStatus.SUCCESS,
                message=f"Created archive at '{dest_path}'",
            )
            return Result(status=ExecutionStatus.SUCCESS, outcomes=[outcome], errors=[])
        except Exception as exc:
            return Result(status=ExecutionStatus.FAILED, errors=[str(exc)])
