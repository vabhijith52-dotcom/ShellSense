"""Filesystem operations (read, modify, trash, undo).

Enforces PathGuard validation, TOCTOU safety, and send2trash integration.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any

import send2trash
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


class FileListParams(BaseModel):
    path: str = Field(default="")


class FileListOperation(BaseOperation):
    """List directory contents within granted roots."""

    def __init__(self) -> None:
        self.guard = PathGuard()

    @property
    def name(self) -> str:
        return "LIST_FILES"

    @property
    def intents(self) -> tuple[str, ...]:
        return ("LIST_FILES",)

    @property
    def params_schema(self) -> type[BaseModel]:
        return FileListParams

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
        roots = [Path(r) for r in (allowed_roots or [])]
        raw_path = params.get("path")
        target_dir = Path(raw_path).expanduser().resolve() if raw_path else (roots[0] if roots else Path.cwd())

        safe, reason = self.guard.validate_path(target_dir, allowed_roots=roots)
        if not safe:
            raise PermissionError(f"Directory access refused: {reason}")

        now = time.time()
        plan_id = f"plan-{uuid.uuid4().hex[:12]}"
        target = TargetFile(
            path=str(target_dir),
            exists=target_dir.exists(),
            is_dir=True,
            inode=target_dir.stat().st_ino if target_dir.exists() else None,
            device=target_dir.stat().st_dev if target_dir.exists() else None,
            mtime=target_dir.stat().st_mtime if target_dir.exists() else None,
        )

        plan_hash = compute_plan_hash(
            operation=self.name,
            target_files=(target,),
            target_processes=(),
            parameters={"path": str(target_dir)},
            risk_level=RiskLevel.SAFE,
            summary=f"List directory contents of '{target_dir}'",
            consequences="Read-only filesystem inspection.",
            created_at=now,
            expires_at=now + 120.0,
        )

        return Plan(
            plan_id=plan_id,
            operation=self.name,
            target_files=(target,),
            target_processes=(),
            parameters={"path": str(target_dir)},
            risk_level=RiskLevel.SAFE,
            summary=f"List directory contents of '{target_dir}'",
            consequences="Read-only filesystem inspection.",
            confirmation_hint=ConfirmationHint(
                kind=ConfirmationKind.NONE,
                token=None,
                prompt_message="Read-only SAFE operation.",
            ),
            created_at=now,
            expires_at=now + 120.0,
            plan_hash=plan_hash,
        )

    def preview(self, plan: Plan) -> dict[str, Any]:
        return {
            "operation": self.name,
            "path": plan.parameters.get("path", ""),
            "risk_level": RiskLevel.SAFE.value,
        }

    def execute(self, approved_plan: ApprovedPlan) -> Result:
        target_dir = Path(approved_plan.plan.parameters.get("path", ""))
        items: list[dict[str, Any]] = []

        try:
            if target_dir.exists() and target_dir.is_dir():
                for entry in target_dir.iterdir():
                    try:
                        st = entry.stat()
                        items.append({
                            "name": entry.name,
                            "path": str(entry.resolve()),
                            "is_dir": entry.is_dir(),
                            "size_bytes": st.st_size if not entry.is_dir() else 0,
                            "mtime": st.st_mtime,
                        })
                    except (PermissionError, OSError):
                        pass

            outcome = TargetOutcome(
                target=str(target_dir),
                status=ExecutionStatus.SUCCESS,
                message=f"Retrieved {len(items)} items from '{target_dir}'",
            )
            return Result(
                status=ExecutionStatus.SUCCESS,
                outcomes=[outcome],
                errors=[],
            )
        except Exception as exc:
            return Result(
                status=ExecutionStatus.FAILED,
                errors=[str(exc)],
            )


class TrashFilesParams(BaseModel):
    targets: list[str] = Field(default_factory=list)


class TrashFilesOperation(BaseOperation):
    """Move files or directories to Trash / Recycle Bin with undo capability."""

    def __init__(self) -> None:
        self.guard = PathGuard()

    @property
    def name(self) -> str:
        return "TRASH_FILES"

    @property
    def intents(self) -> tuple[str, ...]:
        return ("TRASH_FILES", "DELETE_FILES")

    @property
    def params_schema(self) -> type[BaseModel]:
        return TrashFilesParams

    @property
    def required_capability(self) -> Capability:
        return Capability.FILES_TRASH

    def compute_risk(self, params: dict[str, Any]) -> RiskLevel:
        return RiskLevel.DESTRUCTIVE

    def plan(
        self,
        params: dict[str, Any],
        original_text: str = "",
        allowed_roots: list[Any] | None = None,
    ) -> Plan:
        roots = [Path(r) for r in (allowed_roots or [])]
        raw_targets = params.get("targets", [])
        if not raw_targets:
            raise ValueError("No targets specified for deletion.")

        target_files_list: list[TargetFile] = []
        for t in raw_targets:
            p = Path(t).expanduser().resolve()
            safe, reason = self.guard.validate_path(p, allowed_roots=roots)
            if not safe:
                raise PermissionError(f"Target '{p}' is not permitted: {reason}")
            if not p.exists():
                raise FileNotFoundError(f"Target '{p}' does not exist.")

            st = p.stat()
            target_files_list.append(
                TargetFile(
                    path=str(p),
                    exists=True,
                    is_dir=p.is_dir(),
                    size_bytes=st.st_size if not p.is_dir() else None,
                    inode=st.st_ino,
                    device=st.st_dev,
                    mtime=st.st_mtime,
                )
            )

        now = time.time()
        plan_id = f"plan-{uuid.uuid4().hex[:12]}"
        count = len(target_files_list)
        token = target_files_list[0].path if count == 1 else f"DELETE {count}"
        summary = f"Move {count} item{'s' if count != 1 else ''} to Trash / Recycle Bin"
        consequences = (
            "These items will be moved to the Recycle Bin / Trash. "
            "You can undo this operation from History or the Undo toast."
        )

        plan_hash = compute_plan_hash(
            operation=self.name,
            target_files=tuple(target_files_list),
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
            target_files=tuple(target_files_list),
            target_processes=(),
            parameters=params,
            risk_level=RiskLevel.DESTRUCTIVE,
            summary=summary,
            consequences=consequences,
            confirmation_hint=ConfirmationHint(
                kind=ConfirmationKind.TOKEN,
                token=token,
                prompt_message=f"Type '{token}' to confirm moving to Trash.",
            ),
            created_at=now,
            expires_at=now + 120.0,
            plan_hash=plan_hash,
        )

    def preview(self, plan: Plan) -> dict[str, Any]:
        return {
            "operation": self.name,
            "target_count": len(plan.target_files),
            "targets": [f.path for f in plan.target_files],
            "risk_level": RiskLevel.DESTRUCTIVE.value,
            "confirmation_token": plan.confirmation_hint.token,
            "consequences": plan.consequences,
        }

    def execute(self, approved_plan: ApprovedPlan) -> Result:
        outcomes: list[TargetOutcome] = []
        errors: list[str] = []

        for target in approved_plan.plan.target_files:
            try:
                p = Path(target.path)
                send2trash.send2trash(str(p))
                outcomes.append(
                    TargetOutcome(
                        target=target.path,
                        status=ExecutionStatus.SUCCESS,
                        message="Moved to Recycle Bin / Trash.",
                    )
                )
            except Exception as exc:
                errors.append(f"Failed to move '{target.path}' to trash: {exc}")
                outcomes.append(
                    TargetOutcome(
                        target=target.path,
                        status=ExecutionStatus.FAILED,
                        message=str(exc),
                    )
                )

        status = ExecutionStatus.SUCCESS if not errors else (
            ExecutionStatus.PARTIAL if outcomes else ExecutionStatus.FAILED
        )
        return Result(status=status, outcomes=outcomes, errors=errors)
