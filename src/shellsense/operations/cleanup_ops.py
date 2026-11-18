"""Temporary file cleanup operation (DESTRUCTIVE, moves to Trash)."""

from __future__ import annotations

import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

import send2trash
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
    TargetFile,
    TargetOutcome,
    compute_plan_hash,
)
from shellsense.operations.registry import BaseOperation
from shellsense.safety.path_guard import PathGuard


class CleanTempParams(BaseModel):
    max_age_days: int = 1


class CleanTempOperation(BaseOperation):
    """Clean temporary files by moving them to the Trash (DESTRUCTIVE)."""

    def __init__(self) -> None:
        self.guard = PathGuard()

    @property
    def name(self) -> str:
        return "CLEAN_TEMP"

    @property
    def intents(self) -> tuple[str, ...]:
        return ("CLEAN_TEMP",)

    @property
    def params_schema(self) -> type[BaseModel]:
        return CleanTempParams

    @property
    def required_capability(self) -> Capability:
        return Capability.FILES_TRASH

    @property
    def catalog_examples(self) -> tuple[str, ...]:
        return (
            "Delete temporary files",
            "Clean temp",
            "Clean temporary files",
        )

    def compute_risk(self, params: dict[str, Any]) -> RiskLevel:
        return RiskLevel.DESTRUCTIVE

    def plan(
        self,
        params: dict[str, Any],
        original_text: str = "",
        allowed_roots: list[Any] | None = None,
    ) -> Plan:
        roots = [Path(r) for r in (allowed_roots or [])]
        user_temp = Path(tempfile.gettempdir()).resolve()
        cache_thumbs = (Path.home() / ".cache" / "thumbnails").resolve()

        search_dirs = [user_temp]
        if cache_thumbs.exists():
            search_dirs.append(cache_thumbs)
        for r in roots:
            if r not in search_dirs and r.exists():
                search_dirs.append(r)

        candidates: list[TargetFile] = []
        max_age_secs = int(params.get("max_age_days", 1)) * 86400
        cutoff = time.time() - max_age_secs

        for sdir in search_dirs:
            if sdir.exists():
                try:
                    for entry in sdir.glob("*.tmp"):
                        if entry.is_file() and not entry.is_symlink():
                            st = entry.stat()
                            if st.st_mtime <= cutoff or sdir == cache_thumbs:
                                candidates.append(
                                    TargetFile(
                                        path=str(entry.resolve()),
                                        exists=True,
                                        is_dir=False,
                                        size_bytes=st.st_size,
                                        inode=st.st_ino,
                                        device=st.st_dev,
                                        mtime=st.st_mtime,
                                    )
                                )
                                if len(candidates) >= 50:
                                    break
                except (OSError, PermissionError):
                    pass

        now = time.time()
        plan_id = f"plan-{uuid.uuid4().hex[:12]}"
        count = len(candidates)
        token = f"DELETE {count}" if count > 0 else "DELETE 0"
        total_kb = sum(c.size_bytes or 0 for c in candidates) / 1024
        summary = f"Clean up {count} temporary files ({total_kb:.1f} KB)"
        consequences = "Temporary files will be safely moved to the Trash / Recycle Bin."

        plan_hash = compute_plan_hash(
            operation=self.name,
            target_files=tuple(candidates),
            target_processes=(),
            parameters=params,
            risk_level=RiskLevel.DESTRUCTIVE,
            summary=summary,
            consequences=consequences,
            created_at=now,
            expires_at=now + 120.0,
        )

        return Plan(
            plan_id=plan_id,
            operation=self.name,
            target_files=tuple(candidates),
            target_processes=(),
            parameters=params,
            risk_level=RiskLevel.DESTRUCTIVE,
            summary=summary,
            consequences=consequences,
            confirmation_hint=ConfirmationHint(
                kind=ConfirmationKind.TOKEN,
                token=token,
                prompt_message=f"Type '{token}' to confirm moving temporary files to Trash.",
            ),
            created_at=now,
            expires_at=now + 120.0,
            plan_hash=plan_hash,
        )

    def preview(self, plan: Plan) -> dict[str, Any]:
        return {
            "operation": self.name,
            "count": len(plan.target_files),
            "token": plan.confirmation_hint.token,
            "risk_level": RiskLevel.DESTRUCTIVE.value,
        }

    def execute(self, approved_plan: ApprovedPlan) -> Result:
        outcomes: list[TargetOutcome] = []
        errors: list[str] = []

        for target in approved_plan.plan.target_files:
            try:
                send2trash.send2trash(target.path)
                outcomes.append(
                    TargetOutcome(
                        target=target.path,
                        status=ExecutionStatus.SUCCESS,
                        message="Moved temporary file to Trash.",
                    )
                )
            except Exception as exc:
                errors.append(f"Failed to trash '{target.path}': {exc}")

        status = ExecutionStatus.SUCCESS if not errors else (
            ExecutionStatus.PARTIAL if outcomes else ExecutionStatus.FAILED
        )
        return Result(status=status, outcomes=outcomes, errors=errors)
