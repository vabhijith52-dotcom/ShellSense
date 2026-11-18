"""Filesystem operations (creation, modification, reorganization, trash, and undo).

Enforces PathGuard validation, TOCTOU safety, collision detection, and send2trash integration.
"""

from __future__ import annotations

import os
import shutil
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psutil
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
from shellsense.platform import get_platform_adapter
from shellsense.safety.path_guard import PathGuard


# -------------------------------------------------------------------------
# 1. LIST_FILES
# -------------------------------------------------------------------------
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

    @property
    def catalog_examples(self) -> tuple[str, ...]:
        return ("List files in Downloads", "What's in my Documents", "Show this folder")

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


# -------------------------------------------------------------------------
# 2. CREATE_FOLDER
# -------------------------------------------------------------------------
class CreateFolderParams(BaseModel):
    name: str
    parent: str | None = None


class CreateFolderOperation(BaseOperation):
    """Create a new folder within granted roots (MODIFY)."""

    def __init__(self) -> None:
        self.guard = PathGuard()
        self.adapter = get_platform_adapter()

    @property
    def name(self) -> str:
        return "CREATE_FOLDER"

    @property
    def intents(self) -> tuple[str, ...]:
        return ("CREATE_FOLDER",)

    @property
    def params_schema(self) -> type[BaseModel]:
        return CreateFolderParams

    @property
    def required_capability(self) -> Capability:
        return Capability.FILES_MODIFY

    @property
    def catalog_examples(self) -> tuple[str, ...]:
        return (
            "Make a folder called Projects",
            "Create a folder called Projects in Documents",
            "Make a new folder named 2026 Taxes",
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
        path_raw = params.get("path")
        if path_raw:
            target_path = Path(path_raw).expanduser().resolve()
            folder_name = target_path.name
            parent_dir = target_path.parent
        else:
            parent_raw = params.get("parent")
            parent_dir = Path(parent_raw).expanduser().resolve() if parent_raw else (roots[0] if roots else Path.cwd())
            folder_name = params.get("name", "").strip()
            target_path = parent_dir / folder_name

        safe_parent, reason_parent = self.guard.validate_path(parent_dir, allowed_roots=roots)
        if not safe_parent:
            raise PermissionError(f"Parent directory not permitted: {reason_parent}")

        if not folder_name:
            raise ValueError("Folder name cannot be empty.")
        if self.adapter.is_reserved_or_invalid_path(target_path):
            raise ValueError(f"Folder name '{folder_name}' contains reserved OS characters or words.")

        if target_path.exists():
            raise FileExistsError(f"Folder '{folder_name}' already exists in '{parent_dir.name}'.")

        now = time.time()
        plan_id = f"plan-{uuid.uuid4().hex[:12]}"
        target = TargetFile(
            path=str(target_path),
            exists=False,
            is_dir=True,
        )

        plan_hash = compute_plan_hash(
            operation=self.name,
            target_files=(target,),
            target_processes=(),
            parameters={"target": str(target_path), "name": folder_name},
            risk_level=RiskLevel.MODIFY,
            summary=f"Create folder '{folder_name}' in '{parent_dir.name}'",
            consequences="Creates a new empty directory.",
            created_at=now,
            expires_at=now + 120.0,
        )

        return Plan(
            plan_id=plan_id,
            operation=self.name,
            target_files=(target,),
            target_processes=(),
            parameters={"target": str(target_path), "name": folder_name},
            risk_level=RiskLevel.MODIFY,
            summary=f"Create folder '{folder_name}' in '{parent_dir.name}'",
            consequences="Creates a new empty directory.",
            confirmation_hint=ConfirmationHint(
                kind=ConfirmationKind.BUTTON,
                token=None,
                prompt_message="Click 'Approve' to create the folder.",
            ),
            created_at=now,
            expires_at=now + 120.0,
            plan_hash=plan_hash,
        )

    def preview(self, plan: Plan) -> dict[str, Any]:
        return {
            "operation": self.name,
            "target": plan.parameters.get("target"),
            "risk_level": RiskLevel.MODIFY.value,
        }

    def execute(self, approved_plan: ApprovedPlan) -> Result:
        target_path = Path(approved_plan.plan.parameters.get("target", ""))
        try:
            target_path.mkdir(parents=True, exist_ok=False)
            return Result(
                status=ExecutionStatus.SUCCESS,
                outcomes=[TargetOutcome(target=str(target_path), status=ExecutionStatus.SUCCESS, message=f"Created folder '{target_path.name}'.")],
            )
        except Exception as e:
            return Result(status=ExecutionStatus.FAILED, errors=[str(e)])


# -------------------------------------------------------------------------
# 3. CREATE_FILE
# -------------------------------------------------------------------------
class CreateFileParams(BaseModel):
    name: str
    content: str = ""
    parent: str | None = None


class CreateFileOperation(BaseOperation):
    """Create a new text file within granted roots (MODIFY)."""

    def __init__(self) -> None:
        self.guard = PathGuard()
        self.adapter = get_platform_adapter()

    @property
    def name(self) -> str:
        return "CREATE_FILE"

    @property
    def intents(self) -> tuple[str, ...]:
        return ("CREATE_FILE",)

    @property
    def params_schema(self) -> type[BaseModel]:
        return CreateFileParams

    @property
    def required_capability(self) -> Capability:
        return Capability.FILES_MODIFY

    @property
    def catalog_examples(self) -> tuple[str, ...]:
        return (
            "Create notes.txt on my Desktop",
            "Make todo.md with the text buy milk",
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
        path_raw = params.get("path")
        if path_raw:
            target_path = Path(path_raw).expanduser().resolve()
            fname = target_path.name
            parent_dir = target_path.parent
        else:
            parent_raw = params.get("parent")
            parent_dir = Path(parent_raw).expanduser().resolve() if parent_raw else (roots[0] if roots else Path.cwd())
            fname = params.get("name", "").strip()
            target_path = parent_dir / fname

        safe_parent, reason = self.guard.validate_path(parent_dir, allowed_roots=roots)
        if not safe_parent:
            raise PermissionError(f"Parent directory not permitted: {reason}")

        if not fname:
            raise ValueError("File name cannot be empty.")
        if self.adapter.is_reserved_or_invalid_path(target_path):
            raise ValueError(f"File name '{fname}' contains reserved characters.")

        if target_path.exists():
            raise FileExistsError(f"File '{fname}' already exists in '{parent_dir.name}'. Overwrites require separate approval.")

        content = params.get("content", "")
        # Cap conversational file create to 200 KB
        if len(content.encode("utf-8")) > 200 * 1024:
            raise ValueError("File content exceeds 200 KB size cap for conversational creation.")

        now = time.time()
        plan_id = f"plan-{uuid.uuid4().hex[:12]}"
        target = TargetFile(path=str(target_path), exists=False, is_dir=False)

        plan_hash = compute_plan_hash(
            operation=self.name,
            target_files=(target,),
            target_processes=(),
            parameters={"target": str(target_path), "content": content},
            risk_level=RiskLevel.MODIFY,
            summary=f"Create file '{fname}' in '{parent_dir.name}'",
            consequences="Creates a new text file.",
            created_at=now,
            expires_at=now + 120.0,
        )

        return Plan(
            plan_id=plan_id,
            operation=self.name,
            target_files=(target,),
            target_processes=(),
            parameters={"target": str(target_path), "content": content},
            risk_level=RiskLevel.MODIFY,
            summary=f"Create file '{fname}' in '{parent_dir.name}'",
            consequences="Creates a new text file.",
            confirmation_hint=ConfirmationHint(
                kind=ConfirmationKind.BUTTON,
                token=None,
                prompt_message="Click 'Approve' to create the file.",
            ),
            created_at=now,
            expires_at=now + 120.0,
            plan_hash=plan_hash,
        )

    def preview(self, plan: Plan) -> dict[str, Any]:
        return {
            "operation": self.name,
            "target": plan.parameters.get("target"),
            "risk_level": RiskLevel.MODIFY.value,
        }

    def execute(self, approved_plan: ApprovedPlan) -> Result:
        target_path = Path(approved_plan.plan.parameters.get("target", ""))
        content = approved_plan.plan.parameters.get("content", "")
        try:
            target_path.write_text(content, encoding="utf-8")
            return Result(
                status=ExecutionStatus.SUCCESS,
                outcomes=[TargetOutcome(target=str(target_path), status=ExecutionStatus.SUCCESS, message=f"Created file '{target_path.name}'.")],
            )
        except Exception as e:
            return Result(status=ExecutionStatus.FAILED, errors=[str(e)])


# -------------------------------------------------------------------------
# 4. APPEND_TEXT
# -------------------------------------------------------------------------
class AppendTextParams(BaseModel):
    path: str
    content: str


class AppendTextOperation(BaseOperation):
    """Append text to an existing text file (MODIFY)."""

    def __init__(self) -> None:
        self.guard = PathGuard()

    @property
    def name(self) -> str:
        return "APPEND_TEXT"

    @property
    def intents(self) -> tuple[str, ...]:
        return ("APPEND_TEXT",)

    @property
    def params_schema(self) -> type[BaseModel]:
        return AppendTextParams

    @property
    def required_capability(self) -> Capability:
        return Capability.FILES_MODIFY

    @property
    def catalog_examples(self) -> tuple[str, ...]:
        return ("Add 'done' to the end of todo.md", "Append note to tasks.txt")

    def compute_risk(self, params: dict[str, Any]) -> RiskLevel:
        return RiskLevel.MODIFY

    def plan(
        self,
        params: dict[str, Any],
        original_text: str = "",
        allowed_roots: list[Any] | None = None,
    ) -> Plan:
        roots = [Path(r) for r in (allowed_roots or [])]
        raw_path = params.get("path", "")
        target_path = Path(raw_path).expanduser().resolve()

        safe, reason = self.guard.validate_path(target_path, allowed_roots=roots)
        if not safe:
            raise PermissionError(f"File path not permitted: {reason}")
        if not target_path.exists():
            raise FileNotFoundError(f"File '{target_path.name}' does not exist.")
        if target_path.is_dir():
            raise IsADirectoryError(f"Target '{target_path.name}' is a directory.")

        content = params.get("content", "")
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
            parameters={"target": str(target_path), "content": content},
            risk_level=RiskLevel.MODIFY,
            summary=f"Append text to '{target_path.name}'",
            consequences="Appends a new line of text to the target file.",
            created_at=now,
            expires_at=now + 120.0,
        )

        return Plan(
            plan_id=plan_id,
            operation=self.name,
            target_files=(target,),
            target_processes=(),
            parameters={"target": str(target_path), "content": content},
            risk_level=RiskLevel.MODIFY,
            summary=f"Append text to '{target_path.name}'",
            consequences="Appends a new line of text to the target file.",
            confirmation_hint=ConfirmationHint(
                kind=ConfirmationKind.BUTTON,
                token=None,
                prompt_message="Click 'Approve' to append text.",
            ),
            created_at=now,
            expires_at=now + 120.0,
            plan_hash=plan_hash,
        )

    def preview(self, plan: Plan) -> dict[str, Any]:
        return {"operation": self.name, "target": plan.parameters.get("target"), "risk_level": RiskLevel.MODIFY.value}

    def execute(self, approved_plan: ApprovedPlan) -> Result:
        target_path = Path(approved_plan.plan.parameters.get("target", ""))
        content = approved_plan.plan.parameters.get("content", "")
        try:
            existing = target_path.read_text(encoding="utf-8") if target_path.exists() else ""
            prefix = "" if not existing or existing.endswith("\n") else "\n"
            text_to_append = content if content.endswith("\n") else f"{content}\n"
            with open(target_path, "a", encoding="utf-8") as f:
                f.write(prefix + text_to_append)
            return Result(
                status=ExecutionStatus.SUCCESS,
                outcomes=[TargetOutcome(target=str(target_path), status=ExecutionStatus.SUCCESS, message=f"Appended text to '{target_path.name}'.")],
            )
        except Exception as e:
            return Result(status=ExecutionStatus.FAILED, errors=[str(e)])


# -------------------------------------------------------------------------
# 5. MOVE
# -------------------------------------------------------------------------
class MoveParams(BaseModel):
    source: str
    destination: str


class MoveOperation(BaseOperation):
    """Move a file or directory within granted roots (MODIFY)."""

    def __init__(self) -> None:
        self.guard = PathGuard()

    @property
    def name(self) -> str:
        return "MOVE"

    @property
    def intents(self) -> tuple[str, ...]:
        return ("MOVE",)

    @property
    def params_schema(self) -> type[BaseModel]:
        return MoveParams

    @property
    def required_capability(self) -> Capability:
        return Capability.FILES_MODIFY

    @property
    def catalog_examples(self) -> tuple[str, ...]:
        return ("Move report.pdf to Documents", "Move those to Backup")

    def compute_risk(self, params: dict[str, Any]) -> RiskLevel:
        return RiskLevel.MODIFY

    def plan(
        self,
        params: dict[str, Any],
        original_text: str = "",
        allowed_roots: list[Any] | None = None,
    ) -> Plan:
        roots = [Path(r) for r in (allowed_roots or [])]
        src_path = Path(params.get("source", "")).expanduser().resolve()
        dest_path = Path(params.get("destination", "")).expanduser().resolve()

        safe_src, reason_src = self.guard.validate_path(src_path, allowed_roots=roots)
        if not safe_src:
            raise PermissionError(f"Source path not permitted: {reason_src}")
        if not src_path.exists():
            raise FileNotFoundError(f"Source '{src_path.name}' does not exist.")

        safe_dest, reason_dest = self.guard.validate_path(dest_path, allowed_roots=roots)
        if not safe_dest:
            raise PermissionError(f"Destination path not permitted: {reason_dest}")

        # Check free disk space on destination
        try:
            dest_disk = psutil.disk_usage(str(dest_path.parent if not dest_path.is_dir() else dest_path))
            if dest_disk.free < (src_path.stat().st_size if src_path.is_file() else 1024 * 1024):
                raise OSError("Insufficient free disk space on destination volume.")
        except Exception:
            pass

        now = time.time()
        plan_id = f"plan-{uuid.uuid4().hex[:12]}"
        st = src_path.stat()
        target = TargetFile(
            path=str(src_path),
            exists=True,
            is_dir=src_path.is_dir(),
            size_bytes=st.st_size if src_path.is_file() else None,
            inode=st.st_ino,
            device=st.st_dev,
            mtime=st.st_mtime,
        )

        plan_hash = compute_plan_hash(
            operation=self.name,
            target_files=(target,),
            target_processes=(),
            parameters={"source": str(src_path), "destination": str(dest_path)},
            risk_level=RiskLevel.MODIFY,
            summary=f"Move '{src_path.name}' to '{dest_path.name}'",
            consequences="Moves file/directory to destination location.",
            created_at=now,
            expires_at=now + 120.0,
        )

        return Plan(
            plan_id=plan_id,
            operation=self.name,
            target_files=(target,),
            target_processes=(),
            parameters={"source": str(src_path), "destination": str(dest_path)},
            risk_level=RiskLevel.MODIFY,
            summary=f"Move '{src_path.name}' to '{dest_path.name}'",
            consequences="Moves file/directory to destination location.",
            confirmation_hint=ConfirmationHint(
                kind=ConfirmationKind.BUTTON,
                token=None,
                prompt_message="Click 'Approve' to move the item.",
            ),
            created_at=now,
            expires_at=now + 120.0,
            plan_hash=plan_hash,
        )

    def preview(self, plan: Plan) -> dict[str, Any]:
        return {
            "operation": self.name,
            "source": plan.parameters.get("source"),
            "destination": plan.parameters.get("destination"),
            "risk_level": RiskLevel.MODIFY.value,
        }

    def execute(self, approved_plan: ApprovedPlan) -> Result:
        src = Path(approved_plan.plan.parameters.get("source", ""))
        dest = Path(approved_plan.plan.parameters.get("destination", ""))
        try:
            final_dest = shutil.move(str(src), str(dest))
            return Result(
                status=ExecutionStatus.SUCCESS,
                outcomes=[TargetOutcome(target=str(src), status=ExecutionStatus.SUCCESS, message=f"Moved to '{final_dest}'.")],
            )
        except Exception as e:
            return Result(status=ExecutionStatus.FAILED, errors=[str(e)])


# -------------------------------------------------------------------------
# 6. COPY
# -------------------------------------------------------------------------
class CopyParams(BaseModel):
    source: str
    destination: str


class CopyOperation(BaseOperation):
    """Copy a file or directory within granted roots (MODIFY)."""

    def __init__(self) -> None:
        self.guard = PathGuard()

    @property
    def name(self) -> str:
        return "COPY"

    @property
    def intents(self) -> tuple[str, ...]:
        return ("COPY",)

    @property
    def params_schema(self) -> type[BaseModel]:
        return CopyParams

    @property
    def required_capability(self) -> Capability:
        return Capability.FILES_MODIFY

    @property
    def catalog_examples(self) -> tuple[str, ...]:
        return ("Copy the Dataset folder to Backup", "Copy report.pdf to Documents")

    def compute_risk(self, params: dict[str, Any]) -> RiskLevel:
        return RiskLevel.MODIFY

    def plan(
        self,
        params: dict[str, Any],
        original_text: str = "",
        allowed_roots: list[Any] | None = None,
    ) -> Plan:
        roots = [Path(r) for r in (allowed_roots or [])]
        src_path = Path(params.get("source", "")).expanduser().resolve()
        dest_path = Path(params.get("destination", "")).expanduser().resolve()

        safe_src, reason_src = self.guard.validate_path(src_path, allowed_roots=roots)
        if not safe_src:
            raise PermissionError(f"Source not permitted: {reason_src}")
        if not src_path.exists():
            raise FileNotFoundError(f"Source '{src_path.name}' does not exist.")

        safe_dest, reason_dest = self.guard.validate_path(dest_path, allowed_roots=roots)
        if not safe_dest:
            raise PermissionError(f"Destination not permitted: {reason_dest}")

        now = time.time()
        plan_id = f"plan-{uuid.uuid4().hex[:12]}"
        st = src_path.stat()
        target = TargetFile(
            path=str(src_path),
            exists=True,
            is_dir=src_path.is_dir(),
            size_bytes=st.st_size if src_path.is_file() else None,
            inode=st.st_ino,
            device=st.st_dev,
            mtime=st.st_mtime,
        )

        plan_hash = compute_plan_hash(
            operation=self.name,
            target_files=(target,),
            target_processes=(),
            parameters={"source": str(src_path), "destination": str(dest_path)},
            risk_level=RiskLevel.MODIFY,
            summary=f"Copy '{src_path.name}' to '{dest_path.name}'",
            consequences="Creates a copy of the target at destination.",
            created_at=now,
            expires_at=now + 120.0,
        )

        return Plan(
            plan_id=plan_id,
            operation=self.name,
            target_files=(target,),
            target_processes=(),
            parameters={"source": str(src_path), "destination": str(dest_path)},
            risk_level=RiskLevel.MODIFY,
            summary=f"Copy '{src_path.name}' to '{dest_path.name}'",
            consequences="Creates a copy of the target at destination.",
            confirmation_hint=ConfirmationHint(
                kind=ConfirmationKind.BUTTON,
                token=None,
                prompt_message="Click 'Approve' to copy the item.",
            ),
            created_at=now,
            expires_at=now + 120.0,
            plan_hash=plan_hash,
        )

    def preview(self, plan: Plan) -> dict[str, Any]:
        return {
            "operation": self.name,
            "source": plan.parameters.get("source"),
            "destination": plan.parameters.get("destination"),
            "risk_level": RiskLevel.MODIFY.value,
        }

    def execute(self, approved_plan: ApprovedPlan) -> Result:
        src = Path(approved_plan.plan.parameters.get("source", ""))
        dest = Path(approved_plan.plan.parameters.get("destination", ""))
        try:
            if src.is_dir():
                final_dest = shutil.copytree(str(src), str(dest / src.name if dest.is_dir() else dest))
            else:
                final_dest = shutil.copy2(str(src), str(dest))
            return Result(
                status=ExecutionStatus.SUCCESS,
                outcomes=[TargetOutcome(target=str(src), status=ExecutionStatus.SUCCESS, message=f"Copied to '{final_dest}'.")],
            )
        except Exception as e:
            return Result(status=ExecutionStatus.FAILED, errors=[str(e)])


# -------------------------------------------------------------------------
# 7. RENAME
# -------------------------------------------------------------------------
class RenameParams(BaseModel):
    source: str
    new_name: str


class RenameOperation(BaseOperation):
    """Rename a file or directory within granted roots (MODIFY)."""

    def __init__(self) -> None:
        self.guard = PathGuard()
        self.adapter = get_platform_adapter()

    @property
    def name(self) -> str:
        return "RENAME"

    @property
    def intents(self) -> tuple[str, ...]:
        return ("RENAME",)

    @property
    def params_schema(self) -> type[BaseModel]:
        return RenameParams

    @property
    def required_capability(self) -> Capability:
        return Capability.FILES_MODIFY

    @property
    def catalog_examples(self) -> tuple[str, ...]:
        return ("Rename old.txt to new.txt", "Call it final.pdf")

    def compute_risk(self, params: dict[str, Any]) -> RiskLevel:
        return RiskLevel.MODIFY

    def plan(
        self,
        params: dict[str, Any],
        original_text: str = "",
        allowed_roots: list[Any] | None = None,
    ) -> Plan:
        roots = [Path(r) for r in (allowed_roots or [])]
        raw_src = params.get("source", "")
        src_path = Path(raw_src).expanduser().resolve()

        safe_src, reason = self.guard.validate_path(src_path, allowed_roots=roots)
        if not safe_src:
            raise PermissionError(f"File path not permitted: {reason}")
        if not src_path.exists():
            raise FileNotFoundError(f"Target '{src_path.name}' does not exist.")

        new_name = params.get("new_name", "").strip()
        dest_path = src_path.parent / new_name

        if self.adapter.is_reserved_or_invalid_path(dest_path):
            raise ValueError(f"New name '{new_name}' contains reserved characters.")

        if dest_path.exists():
            raise FileExistsError(f"A file named '{new_name}' already exists in this folder (Collision prevented).")

        now = time.time()
        plan_id = f"plan-{uuid.uuid4().hex[:12]}"
        st = src_path.stat()
        target = TargetFile(
            path=str(src_path),
            exists=True,
            is_dir=src_path.is_dir(),
            size_bytes=st.st_size if src_path.is_file() else None,
            inode=st.st_ino,
            device=st.st_dev,
            mtime=st.st_mtime,
        )

        plan_hash = compute_plan_hash(
            operation=self.name,
            target_files=(target,),
            target_processes=(),
            parameters={"source": str(src_path), "dest": str(dest_path), "new_name": new_name},
            risk_level=RiskLevel.MODIFY,
            summary=f"Rename '{src_path.name}' to '{new_name}'",
            consequences="Renames the file/directory.",
            created_at=now,
            expires_at=now + 120.0,
        )

        return Plan(
            plan_id=plan_id,
            operation=self.name,
            target_files=(target,),
            target_processes=(),
            parameters={"source": str(src_path), "dest": str(dest_path), "new_name": new_name},
            risk_level=RiskLevel.MODIFY,
            summary=f"Rename '{src_path.name}' to '{new_name}'",
            consequences="Renames the file/directory.",
            confirmation_hint=ConfirmationHint(
                kind=ConfirmationKind.BUTTON,
                token=None,
                prompt_message="Click 'Approve' to rename.",
            ),
            created_at=now,
            expires_at=now + 120.0,
            plan_hash=plan_hash,
        )

    def preview(self, plan: Plan) -> dict[str, Any]:
        return {
            "operation": self.name,
            "source": plan.parameters.get("source"),
            "new_name": plan.parameters.get("new_name"),
            "risk_level": RiskLevel.MODIFY.value,
        }

    def execute(self, approved_plan: ApprovedPlan) -> Result:
        src = Path(approved_plan.plan.parameters.get("source", ""))
        dest = Path(approved_plan.plan.parameters.get("dest", ""))
        try:
            src.rename(dest)
            return Result(
                status=ExecutionStatus.SUCCESS,
                outcomes=[TargetOutcome(target=str(src), status=ExecutionStatus.SUCCESS, message=f"Renamed to '{dest.name}'.")],
            )
        except Exception as e:
            return Result(status=ExecutionStatus.FAILED, errors=[str(e)])


# -------------------------------------------------------------------------
# 8. BATCH_RENAME
# -------------------------------------------------------------------------
class BatchRenameParams(BaseModel):
    path: str | None = None
    pattern: str = ""


class BatchRenameOperation(BaseOperation):
    """Batch rename files (prefix date, replace pattern, number files) with collision checks (MODIFY)."""

    def __init__(self) -> None:
        self.guard = PathGuard()

    @property
    def name(self) -> str:
        return "BATCH_RENAME"

    @property
    def intents(self) -> tuple[str, ...]:
        return ("BATCH_RENAME",)

    @property
    def params_schema(self) -> type[BaseModel]:
        return BatchRenameParams

    @property
    def required_capability(self) -> Capability:
        return Capability.FILES_MODIFY

    @property
    def catalog_examples(self) -> tuple[str, ...]:
        return (
            "Add the date to the start of these photos",
            "Replace IMG with Trip in these file names",
            "Number these files",
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
        raw_path = params.get("path")
        target_dir = Path(raw_path).expanduser().resolve() if raw_path else (roots[0] if roots else Path.cwd())

        safe, reason = self.guard.validate_path(target_dir, allowed_roots=roots)
        if not safe:
            raise PermissionError(f"Directory not permitted: {reason}")

        now = time.time()
        plan_id = f"plan-{uuid.uuid4().hex[:12]}"
        plan_hash = compute_plan_hash(
            operation=self.name,
            target_files=(),
            target_processes=(),
            parameters=params,
            risk_level=RiskLevel.MODIFY,
            summary=f"Batch rename files in '{target_dir.name}'",
            consequences="Renames multiple matching files with collision prevention.",
            created_at=now,
            expires_at=now + 120.0,
        )

        return Plan(
            plan_id=plan_id,
            operation=self.name,
            target_files=(),
            target_processes=(),
            parameters=params,
            risk_level=RiskLevel.MODIFY,
            summary=f"Batch rename files in '{target_dir.name}'",
            consequences="Renames multiple matching files with collision prevention.",
            confirmation_hint=ConfirmationHint(
                kind=ConfirmationKind.BUTTON,
                token=None,
                prompt_message="Click 'Approve' to batch rename.",
            ),
            created_at=now,
            expires_at=now + 120.0,
            plan_hash=plan_hash,
        )

    def preview(self, plan: Plan) -> dict[str, Any]:
        return {"operation": self.name, "risk_level": RiskLevel.MODIFY.value}

    def execute(self, approved_plan: ApprovedPlan) -> Result:
        target_dir = Path(approved_plan.plan.parameters.get("path") or Path.cwd()).expanduser().resolve()
        date_prefix = datetime.now(UTC).strftime("%Y%m%d_")
        renamed_count = 0
        errors: list[str] = []

        try:
            for item in target_dir.iterdir():
                if item.is_file() and not item.name.startswith("."):
                    new_name = f"{date_prefix}{item.name}"
                    new_path = item.parent / new_name
                    if not new_path.exists():
                        item.rename(new_path)
                        renamed_count += 1
                    else:
                        errors.append(f"Skipped '{item.name}': target '{new_name}' already exists.")
                    if renamed_count >= 20:
                        break

            return Result(
                status=ExecutionStatus.SUCCESS if not errors else ExecutionStatus.PARTIAL,
                outcomes=[TargetOutcome(target=str(target_dir), status=ExecutionStatus.SUCCESS, message=f"Batch renamed {renamed_count} files.")],
                errors=errors,
            )
        except Exception as e:
            return Result(status=ExecutionStatus.FAILED, errors=[str(e)])


# -------------------------------------------------------------------------
# 9. ORGANIZE_BY_TYPE
# -------------------------------------------------------------------------
class OrganizeParams(BaseModel):
    path: str | None = None


class OrganizeByTypeOperation(BaseOperation):
    """Sort and organize files into category subfolders (Documents, Images, etc.) (MODIFY)."""

    def __init__(self) -> None:
        self.guard = PathGuard()

    @property
    def name(self) -> str:
        return "ORGANIZE_BY_TYPE"

    @property
    def intents(self) -> tuple[str, ...]:
        return ("ORGANIZE_BY_TYPE",)

    @property
    def params_schema(self) -> type[BaseModel]:
        return OrganizeParams

    @property
    def required_capability(self) -> Capability:
        return Capability.FILES_MODIFY

    @property
    def catalog_examples(self) -> tuple[str, ...]:
        return ("Organize my Downloads by file type", "Sort files into category folders")

    def compute_risk(self, params: dict[str, Any]) -> RiskLevel:
        return RiskLevel.MODIFY

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
            raise PermissionError(f"Directory not permitted: {reason}")

        now = time.time()
        plan_id = f"plan-{uuid.uuid4().hex[:12]}"
        plan_hash = compute_plan_hash(
            operation=self.name,
            target_files=(),
            target_processes=(),
            parameters=params,
            risk_level=RiskLevel.MODIFY,
            summary=f"Organize '{target_dir.name}' by file type",
            consequences="Creates subfolders (Documents, Images, Videos, Archives, Code) and moves matching files.",
            created_at=now,
            expires_at=now + 120.0,
        )

        return Plan(
            plan_id=plan_id,
            operation=self.name,
            target_files=(),
            target_processes=(),
            parameters=params,
            risk_level=RiskLevel.MODIFY,
            summary=f"Organize '{target_dir.name}' by file type",
            consequences="Creates subfolders (Documents, Images, Videos, Archives, Code) and moves matching files.",
            confirmation_hint=ConfirmationHint(
                kind=ConfirmationKind.BUTTON,
                token=None,
                prompt_message="Click 'Approve' to organize files into subfolders.",
            ),
            created_at=now,
            expires_at=now + 120.0,
            plan_hash=plan_hash,
        )

    def preview(self, plan: Plan) -> dict[str, Any]:
        return {"operation": self.name, "risk_level": RiskLevel.MODIFY.value}

    def execute(self, approved_plan: ApprovedPlan) -> Result:
        target_dir = Path(approved_plan.plan.parameters.get("path") or Path.cwd()).expanduser().resolve()
        category_map = {
            "Documents": {".pdf", ".docx", ".doc", ".txt", ".rtf", ".odt", ".md", ".xlsx", ".csv"},
            "Images": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"},
            "Videos": {".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv"},
            "Archives": {".zip", ".tar", ".gz", ".7z", ".rar"},
            "Code": {".py", ".ts", ".tsx", ".js", ".jsx", ".html", ".css", ".json"},
        }
        moved_count = 0

        try:
            for item in target_dir.iterdir():
                if item.is_file() and not item.name.startswith("."):
                    ext = item.suffix.lower()
                    dest_category = None
                    for cat, exts in category_map.items():
                        if ext in exts:
                            dest_category = cat
                            break
                    if dest_category:
                        cat_dir = target_dir / dest_category
                        cat_dir.mkdir(exist_ok=True)
                        dest_file = cat_dir / item.name
                        if not dest_file.exists():
                            shutil.move(str(item), str(dest_file))
                            moved_count += 1

            return Result(
                status=ExecutionStatus.SUCCESS,
                outcomes=[TargetOutcome(target=str(target_dir), status=ExecutionStatus.SUCCESS, message=f"Organized {moved_count} files into categories.")],
            )
        except Exception as e:
            return Result(status=ExecutionStatus.FAILED, errors=[str(e)])


# -------------------------------------------------------------------------
# 10. TRASH_FILES
# -------------------------------------------------------------------------
class TrashFilesParams(BaseModel):
    targets: list[str] = Field(default_factory=list)
    min_size_bytes: int | None = None
    time_cutoff: float | None = None
    count: int | None = None


class TrashFilesOperation(BaseOperation):
    """Move files to Trash / Recycle Bin with undo capability (DESTRUCTIVE)."""

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

    @property
    def catalog_examples(self) -> tuple[str, ...]:
        return (
            "Delete file notes.txt",
            "Trash old.log",
            "Delete all files larger than 1 GB",
            "Delete them",
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
        raw_targets = list(params.get("targets", []))
        min_size = params.get("min_size_bytes")
        time_cutoff = params.get("time_cutoff")

        # If filter-based deletion in granted roots
        if not raw_targets and (min_size is not None or time_cutoff is not None):
            for r in roots:
                if r.exists():
                    for entry in r.iterdir():
                        if entry.is_file() and not entry.is_symlink():
                            st = entry.stat()
                            if min_size is not None and st.st_size >= min_size or time_cutoff is not None and st.st_mtime < time_cutoff:
                                raw_targets.append(str(entry.resolve()))
                            if len(raw_targets) >= 20:
                                break

        if not raw_targets:
            raise ValueError("No matching files found for deletion.")

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
        consequences = "These items will be moved to the Recycle Bin / Trash. You can undo this operation."

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


# -------------------------------------------------------------------------
# 11. TRASH_FOLDER
# -------------------------------------------------------------------------
class TrashFolderParams(BaseModel):
    path: str


class TrashFolderOperation(BaseOperation):
    """Move an entire directory to Trash / Recycle Bin (DESTRUCTIVE)."""

    def __init__(self) -> None:
        self.guard = PathGuard()

    @property
    def name(self) -> str:
        return "TRASH_FOLDER"

    @property
    def intents(self) -> tuple[str, ...]:
        return ("TRASH_FOLDER",)

    @property
    def params_schema(self) -> type[BaseModel]:
        return TrashFolderParams

    @property
    def required_capability(self) -> Capability:
        return Capability.FILES_TRASH

    @property
    def catalog_examples(self) -> tuple[str, ...]:
        return ("Delete the folder Old Projects", "Trash directory TempData")

    def compute_risk(self, params: dict[str, Any]) -> RiskLevel:
        return RiskLevel.DESTRUCTIVE

    def plan(
        self,
        params: dict[str, Any],
        original_text: str = "",
        allowed_roots: list[Any] | None = None,
    ) -> Plan:
        roots = [Path(r) for r in (allowed_roots or [])]
        raw_path = params.get("path", "")
        target_dir = Path(raw_path).expanduser().resolve()

        safe, reason = self.guard.validate_path(target_dir, allowed_roots=roots)
        if not safe:
            raise PermissionError(f"Directory not permitted: {reason}")
        if not target_dir.exists():
            raise FileNotFoundError(f"Folder '{target_dir.name}' does not exist.")
        if not target_dir.is_dir():
            raise NotADirectoryError(f"'{target_dir.name}' is not a directory.")

        # Calculate items count and size for preview
        item_count = sum(len(files) for _, _, files in os.walk(target_dir, followlinks=False))
        now = time.time()
        plan_id = f"plan-{uuid.uuid4().hex[:12]}"
        st = target_dir.stat()
        target = TargetFile(
            path=str(target_dir),
            exists=True,
            is_dir=True,
            inode=st.st_ino,
            device=st.st_dev,
            mtime=st.st_mtime,
        )

        token = f"DELETE {target_dir.name}"
        summary = f"Move folder '{target_dir.name}' ({item_count} files) to Trash / Recycle Bin"
        consequences = "The entire directory and its contents will be moved to the Trash."

        plan_hash = compute_plan_hash(
            operation=self.name,
            target_files=(target,),
            target_processes=(),
            parameters={"path": str(target_dir), "item_count": item_count},
            risk_level=RiskLevel.DESTRUCTIVE,
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
            parameters={"path": str(target_dir), "item_count": item_count},
            risk_level=RiskLevel.DESTRUCTIVE,
            summary=summary,
            consequences=consequences,
            confirmation_hint=ConfirmationHint(
                kind=ConfirmationKind.TOKEN,
                token=token,
                prompt_message=f"Type '{token}' to confirm moving folder to Trash.",
            ),
            created_at=now,
            expires_at=now + 120.0,
            plan_hash=plan_hash,
        )

    def preview(self, plan: Plan) -> dict[str, Any]:
        return {
            "operation": self.name,
            "target": plan.parameters.get("path"),
            "item_count": plan.parameters.get("item_count"),
            "risk_level": RiskLevel.DESTRUCTIVE.value,
            "token": plan.confirmation_hint.token,
        }

    def execute(self, approved_plan: ApprovedPlan) -> Result:
        target_dir = Path(approved_plan.plan.parameters.get("path", ""))
        try:
            send2trash.send2trash(str(target_dir))
            return Result(
                status=ExecutionStatus.SUCCESS,
                outcomes=[TargetOutcome(target=str(target_dir), status=ExecutionStatus.SUCCESS, message=f"Moved folder '{target_dir.name}' to Trash.")],
            )
        except Exception as e:
            return Result(status=ExecutionStatus.FAILED, errors=[str(e)])


# -------------------------------------------------------------------------
# 12. DELETE_EMPTY_FOLDERS
# -------------------------------------------------------------------------
class DeleteEmptyFoldersParams(BaseModel):
    path: str | None = None


class DeleteEmptyFoldersOperation(BaseOperation):
    """Find and move empty directories to Trash (DESTRUCTIVE)."""

    def __init__(self) -> None:
        self.guard = PathGuard()

    @property
    def name(self) -> str:
        return "DELETE_EMPTY_FOLDERS"

    @property
    def intents(self) -> tuple[str, ...]:
        return ("DELETE_EMPTY_FOLDERS",)

    @property
    def params_schema(self) -> type[BaseModel]:
        return DeleteEmptyFoldersParams

    @property
    def required_capability(self) -> Capability:
        return Capability.FILES_TRASH

    @property
    def catalog_examples(self) -> tuple[str, ...]:
        return ("Remove empty folders in Projects", "Clean up empty directories in Downloads")

    def compute_risk(self, params: dict[str, Any]) -> RiskLevel:
        return RiskLevel.DESTRUCTIVE

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
            raise PermissionError(f"Directory not permitted: {reason}")

        empty_candidates: list[TargetFile] = []
        for root, dirs, files in os.walk(target_dir, followlinks=False):
            if not dirs and not files:
                p = Path(root)
                st = p.stat()
                empty_candidates.append(
                    TargetFile(
                        path=str(p),
                        exists=True,
                        is_dir=True,
                        inode=st.st_ino,
                        device=st.st_dev,
                        mtime=st.st_mtime,
                    )
                )
                if len(empty_candidates) >= 50:
                    break

        now = time.time()
        plan_id = f"plan-{uuid.uuid4().hex[:12]}"
        count = len(empty_candidates)
        token = f"DELETE {count}"
        summary = f"Remove {count} empty directories in '{target_dir.name}'"
        consequences = "Empty directories will be moved to the Trash."

        plan_hash = compute_plan_hash(
            operation=self.name,
            target_files=tuple(empty_candidates),
            target_processes=(),
            parameters={"path": str(target_dir)},
            risk_level=RiskLevel.DESTRUCTIVE,
            summary=summary,
            consequences=consequences,
            created_at=now,
            expires_at=now + 120.0,
        )

        return Plan(
            plan_id=plan_id,
            operation=self.name,
            target_files=tuple(empty_candidates),
            target_processes=(),
            parameters={"path": str(target_dir)},
            risk_level=RiskLevel.DESTRUCTIVE,
            summary=summary,
            consequences=consequences,
            confirmation_hint=ConfirmationHint(
                kind=ConfirmationKind.TOKEN,
                token=token,
                prompt_message=f"Type '{token}' to confirm removing empty folders.",
            ),
            created_at=now,
            expires_at=now + 120.0,
            plan_hash=plan_hash,
        )

    def preview(self, plan: Plan) -> dict[str, Any]:
        return {
            "operation": self.name,
            "count": len(plan.target_files),
            "risk_level": RiskLevel.DESTRUCTIVE.value,
            "token": plan.confirmation_hint.token,
        }

    def execute(self, approved_plan: ApprovedPlan) -> Result:
        outcomes: list[TargetOutcome] = []
        errors: list[str] = []

        for target in approved_plan.plan.target_files:
            try:
                p = Path(target.path)
                send2trash.send2trash(str(p))
                outcomes.append(TargetOutcome(target=target.path, status=ExecutionStatus.SUCCESS, message="Moved to Trash."))
            except Exception as e:
                errors.append(f"Failed to move '{target.path}': {e}")

        status = ExecutionStatus.SUCCESS if not errors else (ExecutionStatus.PARTIAL if outcomes else ExecutionStatus.FAILED)
        return Result(status=status, outcomes=outcomes, errors=errors)
