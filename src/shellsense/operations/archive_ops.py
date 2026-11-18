"""Archive operations (create zip backup archive and safe unzip extraction).

Enforces zip-slip prevention, zip-bomb size/ratio limits, and symlink protection.
"""

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

    @property
    def catalog_examples(self) -> tuple[str, ...]:
        return (
            "Zip my Projects folder",
            "Compress these files",
            "Create archive of documents",
        )

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
        consequences = f"Will compress target into '{dest_path}' (skipping archive if inside itself)."

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
                    for root, _, files in os.walk(target_path, followlinks=False):
                        for file in files:
                            full_path = (Path(root) / file).resolve()
                            # Never include the archive inside itself!
                            if full_path == dest_path.resolve():
                                continue
                            zipf.write(full_path, full_path.relative_to(target_path))
                else:
                    zipf.write(target_path, target_path.name)

            outcome = TargetOutcome(
                target=str(dest_path),
                status=ExecutionStatus.SUCCESS,
                message=f"Created archive at '{dest_path.name}'.",
            )
            return Result(status=ExecutionStatus.SUCCESS, outcomes=[outcome], errors=[])
        except Exception as exc:
            return Result(status=ExecutionStatus.FAILED, errors=[str(exc)])


class ExtractArchiveParams(BaseModel):
    target: str = Field(default="")
    destination: str | None = None


class ExtractArchiveOperation(BaseOperation):
    """Extract zip archive with zip-slip and zip-bomb protection (MODIFY)."""

    def __init__(self) -> None:
        self.guard = PathGuard()

    @property
    def name(self) -> str:
        return "EXTRACT_ARCHIVE"

    @property
    def intents(self) -> tuple[str, ...]:
        return ("EXTRACT_ARCHIVE",)

    @property
    def params_schema(self) -> type[BaseModel]:
        return ExtractArchiveParams

    @property
    def required_capability(self) -> Capability:
        return Capability.FILES_MODIFY

    @property
    def catalog_examples(self) -> tuple[str, ...]:
        return (
            "Unzip backup.zip here",
            "Extract model.zip to Documents",
        )

    def compute_risk(self, params: dict[str, Any]) -> RiskLevel:
        return RiskLevel.MODIFY

    def plan(
        self,
        params: dict[str, Any],
        original_text: str = "",
        allowed_roots: list[Any] | None = None,
    ) -> Plan:
        roots = [Path(r) for r in (allowed_roots or [])]
        raw_target = params.get("target") or ""
        target_path = Path(raw_target).expanduser().resolve()

        safe, reason = self.guard.validate_path(target_path, allowed_roots=roots)
        if not safe:
            raise PermissionError(f"Archive file not permitted: {reason}")
        if not target_path.exists():
            raise FileNotFoundError(f"Archive '{target_path.name}' does not exist.")

        raw_dest = params.get("destination")
        dest_dir = Path(raw_dest).expanduser().resolve() if raw_dest else target_path.parent
        safe_dest, reason_dest = self.guard.validate_path(dest_dir, allowed_roots=roots)
        if not safe_dest:
            raise PermissionError(f"Destination directory not permitted: {reason_dest}")

        # Pre-scan archive to verify zip-slip and limits
        with zipfile.ZipFile(target_path, "r") as zf:
            members = zf.infolist()
            if len(members) > 10_000:
                raise ValueError(f"Archive contains {len(members)} entries (exceeds 10,000 member cap).")

            total_uncompressed = sum(m.file_size for m in members)
            if total_uncompressed > 2 * 1024 * 1024 * 1024:
                raise ValueError("Archive uncompressed size exceeds 2 GB cap.")

            # Zip bomb ratio check
            archive_size = target_path.stat().st_size
            if archive_size > 0 and (total_uncompressed / archive_size) > 100:
                raise ValueError("Archive compression ratio exceeds 100:1 (potential zip bomb).")

            dest_resolved = dest_dir.resolve()
            for m in members:
                # Zip-slip protection check
                member_target = (dest_resolved / m.filename).resolve()
                if not member_target.is_relative_to(dest_resolved):
                    raise PermissionError(f"Malicious zip-slip path traversal detected in member '{m.filename}'.")

        now = time.time()
        plan_id = f"plan-{uuid.uuid4().hex[:12]}"
        st = target_path.stat()
        target = TargetFile(
            path=str(target_path),
            exists=True,
            is_dir=False,
            size_bytes=st.st_size,
            inode=st.st_ino,
            device=st.st_dev,
            mtime=st.st_mtime,
        )

        plan_hash = compute_plan_hash(
            operation=self.name,
            target_files=(target,),
            target_processes=(),
            parameters={"target": str(target_path), "destination": str(dest_dir)},
            risk_level=RiskLevel.MODIFY,
            summary=f"Extract archive '{target_path.name}' into '{dest_dir.name}'",
            consequences="Extracts files with strict zip-slip and size validations.",
            created_at=now,
            expires_at=now + 120.0,
        )

        return Plan(
            plan_id=plan_id,
            operation=self.name,
            target_files=(target,),
            target_processes=(),
            parameters={"target": str(target_path), "destination": str(dest_dir)},
            risk_level=RiskLevel.MODIFY,
            summary=f"Extract archive '{target_path.name}' into '{dest_dir.name}'",
            consequences="Extracts files with strict zip-slip and size validations.",
            confirmation_hint=ConfirmationHint(
                kind=ConfirmationKind.BUTTON,
                token=None,
                prompt_message="Click approve to extract archive.",
            ),
            created_at=now,
            expires_at=now + 120.0,
            plan_hash=plan_hash,
        )

    def preview(self, plan: Plan) -> dict[str, Any]:
        return {
            "operation": self.name,
            "target": plan.parameters.get("target"),
            "destination": plan.parameters.get("destination"),
            "risk_level": RiskLevel.MODIFY.value,
        }

    def execute(self, approved_plan: ApprovedPlan) -> Result:
        target_path = Path(approved_plan.plan.parameters["target"])
        dest_dir = Path(approved_plan.plan.parameters["destination"])

        try:
            dest_resolved = dest_dir.resolve()
            extracted_count = 0
            with zipfile.ZipFile(target_path, "r") as zf:
                for member in zf.infolist():
                    member_path = (dest_resolved / member.filename).resolve()
                    # Invariant: Re-verify zip slip immediately before extracting each member
                    if not member_path.is_relative_to(dest_resolved):
                        return Result(status=ExecutionStatus.FAILED, errors=[f"Security violation: zip-slip in '{member.filename}'."])

                    # Skip symlink members (external_attr check)
                    is_symlink = (member.external_attr >> 16) & 0o120000 == 0o120000
                    if is_symlink:
                        continue

                    zf.extract(member, dest_resolved)
                    extracted_count += 1

            return Result(
                status=ExecutionStatus.SUCCESS,
                outcomes=[TargetOutcome(target=str(dest_dir), status=ExecutionStatus.SUCCESS, message=f"Extracted {extracted_count} files to '{dest_dir.name}'.")],
            )
        except Exception as exc:
            return Result(status=ExecutionStatus.FAILED, errors=[str(exc)])
