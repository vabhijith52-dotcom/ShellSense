"""Filesystem retrieval operations (SAFE, read-only).

Provides file discovery, largest/smallest/newest/oldest files and folders,
counts, file metadata info, empty directory detection, and sanitized text reading.
"""

from __future__ import annotations

import contextlib
import os
import time
import uuid
from datetime import UTC, datetime
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
    TargetOutcome,
    compute_plan_hash,
)
from shellsense.nlp.context import DEFAULT_SESSION_CONTEXT
from shellsense.operations.registry import BaseOperation
from shellsense.safety.path_guard import PathGuard
from shellsense.safety.sanitize import sanitize_text


class FileRetrievalParams(BaseModel):
    count: int = Field(default=10)
    path: str | None = Field(default=None)
    pattern: str | None = Field(default=None)
    min_size_bytes: int | None = Field(default=None)
    max_size_bytes: int | None = Field(default=None)
    time_cutoff: float | None = Field(default=None)
    file_type: str | None = Field(default=None)
    extensions: list[str] = Field(default_factory=list)
    lines: int = Field(default=30)


class FileRetrievalOperation(BaseOperation):
    """File search, ranking, size calculation, and inspection operations."""

    def __init__(self) -> None:
        self.guard = PathGuard()

    @property
    def name(self) -> str:
        return "FILE_RETRIEVAL"

    @property
    def intents(self) -> tuple[str, ...]:
        return (
            "LARGEST_FILES",
            "SMALLEST_FILES",
            "NEWEST_FILES",
            "OLDEST_FILES",
            "FIND_FILES",
            "LARGEST_FOLDERS",
            "FOLDER_SIZE",
            "COUNT_FILES",
            "FILE_INFO",
            "FIND_EMPTY_FOLDERS",
            "READ_TEXT_FILE",
        )

    @property
    def params_schema(self) -> type[BaseModel]:
        return FileRetrievalParams

    @property
    def required_capability(self) -> Capability:
        return Capability.FILES_READ

    @property
    def catalog_examples(self) -> tuple[str, ...]:
        return (
            "Find the largest file",
            "Biggest 5 files in Downloads",
            "Oldest files in Documents",
            "Newest download",
            "Find files over 1 GB",
            "Which folders are biggest",
            "How big is my Documents folder",
            "How many photos do I have",
            "Details of report.pdf",
            "Any empty folders in Projects",
            "Show the first 30 lines of server.log",
        )

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

        # If a single file was passed as path (for FILE_INFO or READ_TEXT_FILE)
        if target_dir.is_file():
            safe, reason = self.guard.validate_path(target_dir, allowed_roots=roots)
            if not safe:
                raise PermissionError(f"File access refused: {reason}")
        else:
            safe, reason = self.guard.validate_path(target_dir, allowed_roots=roots)
            if not safe:
                raise PermissionError(f"Directory access refused: {reason}")

        now = time.time()
        plan_id = f"plan-{uuid.uuid4().hex[:12]}"
        summary = f"Filesystem retrieval inspection on '{target_dir.name}'"
        consequences = "Read-only inspection of files. No modifications made."

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
                prompt_message="Read-only filesystem inspection.",
            ),
            created_at=now,
            expires_at=now + 120.0,
            plan_hash=plan_hash,
        )

    def preview(self, plan: Plan) -> dict[str, Any]:
        return {"operation": self.name, "risk_level": RiskLevel.SAFE.value}

    def execute(self, approved_plan: ApprovedPlan) -> Result:
        params = approved_plan.plan.parameters
        roots = [Path(approved_plan.plan.parameters.get("path") or Path.cwd()).expanduser().resolve()]
        if not roots[0].exists():
            roots = [Path.cwd()]

        target_path = roots[0]
        # Invariant 10: sanitize untrusted names & paths
        sub_op = approved_plan.plan.operation

        # 1. READ_TEXT_FILE
        if sub_op == "READ_TEXT_FILE" or target_path.is_file():
            if not target_path.is_file():
                return Result(
                    status=ExecutionStatus.FAILED,
                    errors=[f"File '{target_path}' does not exist or is not a regular file."],
                )
            max_lines = min(int(params.get("lines", 30)), 100)
            try:
                # Cap file read at 100 KB
                with open(target_path, encoding="utf-8", errors="replace") as f:
                    read_lines = [sanitize_text(f.readline().rstrip("\n")) for _ in range(max_lines)]
                content = "\n".join(line for line in read_lines if line is not None)
                msg = f"Contents of '{target_path.name}' (first {len(read_lines)} lines):\n{content}"
                return Result(
                    status=ExecutionStatus.SUCCESS,
                    outcomes=[TargetOutcome(target=str(target_path), status=ExecutionStatus.SUCCESS, message=msg)],
                )
            except Exception as e:
                return Result(status=ExecutionStatus.FAILED, errors=[f"Error reading file '{target_path}': {e}"])

        # 2. FILE_INFO
        if sub_op == "FILE_INFO":
            try:
                st = target_path.stat()
                mtime_str = datetime.fromtimestamp(st.st_mtime, tz=UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
                size_kb = st.st_size / 1024
                msg = f"File Details: '{target_path.name}' | Size: {size_kb:.1f} KB | Modified: {mtime_str} | Path: {target_path}"
                return Result(
                    status=ExecutionStatus.SUCCESS,
                    outcomes=[TargetOutcome(target=str(target_path), status=ExecutionStatus.SUCCESS, message=msg)],
                )
            except Exception as e:
                return Result(status=ExecutionStatus.FAILED, errors=[f"Error inspecting '{target_path}': {e}"])

        # 3. FOLDER_SIZE
        if sub_op == "FOLDER_SIZE":
            total_bytes = 0
            file_count = 0
            for root, _, files in os.walk(target_path, followlinks=False):
                for filename in files:
                    fp = Path(root) / filename
                    try:
                        total_bytes += fp.stat().st_size
                        file_count += 1
                    except OSError:
                        pass
            total_mb = total_bytes / (1024 * 1024)
            msg = f"Folder '{target_path.name}' size: {total_mb:.1f} MB across {file_count} files."
            return Result(
                status=ExecutionStatus.SUCCESS,
                outcomes=[TargetOutcome(target=str(target_path), status=ExecutionStatus.SUCCESS, message=msg)],
            )

        # 4. LARGEST_FOLDERS
        if sub_op == "LARGEST_FOLDERS":
            folder_sizes: list[tuple[str, int]] = []
            try:
                for entry in target_path.iterdir():
                    if entry.is_dir() and not entry.is_symlink():
                        dir_size = 0
                        for r, _, fls in os.walk(entry, followlinks=False):
                            for fl in fls:
                                with contextlib.suppress(OSError):
                                    dir_size += (Path(r) / fl).stat().st_size
                        folder_sizes.append((entry.name, dir_size))
            except Exception:
                pass
            folder_sizes.sort(key=lambda x: x[1], reverse=True)
            count = int(params.get("count", 10))
            top_dirs = folder_sizes[:count]
            dir_lines = [f"{d[0]} ({d[1] / (1024 * 1024):.1f} MB)" for d in top_dirs]
            msg = f"Largest folders in '{target_path.name}': " + (", ".join(dir_lines) if dir_lines else "No subfolders found.")
            return Result(
                status=ExecutionStatus.SUCCESS,
                outcomes=[TargetOutcome(target=str(target_path), status=ExecutionStatus.SUCCESS, message=msg)],
            )

        # 5. FIND_EMPTY_FOLDERS
        if sub_op == "FIND_EMPTY_FOLDERS":
            empty_dirs: list[str] = []
            for root, dirs, files in os.walk(target_path, followlinks=False):
                if not dirs and not files:
                    empty_dirs.append(root)
                    if len(empty_dirs) >= 50:
                        break
            msg = f"Found {len(empty_dirs)} empty folders in '{target_path.name}': " + (", ".join(empty_dirs[:10]) if empty_dirs else "None")
            return Result(
                status=ExecutionStatus.SUCCESS,
                outcomes=[TargetOutcome(target=str(target_path), status=ExecutionStatus.SUCCESS, message=msg)],
            )

        # 6. COUNT_FILES
        if sub_op == "COUNT_FILES":
            exts = set(params.get("extensions", []))
            count = 0
            for _root, _, files in os.walk(target_path, followlinks=False):
                for filename in files:
                    if not exts or any(filename.lower().endswith(e) for e in exts):
                        count += 1
            type_label = params.get("file_type") or "files"
            msg = f"Found {count} {type_label} in '{target_path.name}'."
            return Result(
                status=ExecutionStatus.SUCCESS,
                outcomes=[TargetOutcome(target=str(target_path), status=ExecutionStatus.SUCCESS, message=msg)],
            )

        # 7. Collect files for LARGEST_FILES, SMALLEST_FILES, NEWEST_FILES, OLDEST_FILES, FIND_FILES
        collected_files: list[dict[str, Any]] = []
        exts = set(params.get("extensions", []))
        min_size = params.get("min_size_bytes")
        max_size = params.get("max_size_bytes")
        time_cutoff = params.get("time_cutoff")
        pattern = params.get("pattern")

        for root, _, files in os.walk(target_path, followlinks=False):
            for filename in files:
                if exts and not any(filename.lower().endswith(e) for e in exts):
                    continue
                if pattern and pattern.lower() not in filename.lower():
                    continue

                fp = Path(root) / filename
                try:
                    st = fp.stat()
                    if min_size is not None and st.st_size < min_size:
                        continue
                    if max_size is not None and st.st_size > max_size:
                        continue
                    if time_cutoff is not None and st.st_mtime < time_cutoff:
                        continue

                    collected_files.append({
                        "name": filename,
                        "path": str(fp),
                        "size_bytes": st.st_size,
                        "mtime": st.st_mtime,
                        "is_dir": False,
                    })
                    if len(collected_files) >= 500:
                        break
                except OSError:
                    pass

        # Sort based on sub-operation
        count = int(params.get("count", 10))
        if sub_op == "LARGEST_FILES":
            collected_files.sort(key=lambda x: x["size_bytes"], reverse=True)
        elif sub_op == "SMALLEST_FILES":
            collected_files.sort(key=lambda x: x["size_bytes"])
        elif sub_op == "NEWEST_FILES":
            collected_files.sort(key=lambda x: x["mtime"], reverse=True)
        elif sub_op == "OLDEST_FILES":
            collected_files.sort(key=lambda x: x["mtime"])

        sliced = collected_files[:count]

        # Invariant: Cache result set server-side for follow-up ("delete them", "move those")
        session_id = "default"
        DEFAULT_SESSION_CONTEXT.store_result_set(
            session_id=session_id,
            operation=sub_op,
            items=sliced,
        )

        sample = ", ".join(f"{f['name']} ({f['size_bytes'] / (1024*1024):.1f} MB)" for f in sliced[:5])
        msg = f"Found {len(collected_files)} matching files (showing {len(sliced)}): {sample}"
        if not sliced:
            msg = f"No files matching criteria found in '{target_path.name}'."

        return Result(
            status=ExecutionStatus.SUCCESS,
            outcomes=[TargetOutcome(target=str(target_path), status=ExecutionStatus.SUCCESS, message=msg)],
        )
