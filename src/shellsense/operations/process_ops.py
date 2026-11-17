"""Process operations (list, inspect, terminate).

Enforces PID safety checks, user ownership verification, and create_time TOCTOU guards.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

import psutil
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
    TargetProcess,
    compute_plan_hash,
)
from shellsense.operations.registry import BaseOperation
from shellsense.platform import get_platform_adapter
from shellsense.safety.sanitize import sanitize_text


class ListProcessesParams(BaseModel):
    limit: int = Field(default=50)


class ListProcessesOperation(BaseOperation):
    """List running processes (SAFE, read-only)."""

    @property
    def name(self) -> str:
        return "LIST_PROCESSES"

    @property
    def intents(self) -> tuple[str, ...]:
        return ("LIST_PROCESSES", "TOP_PROCESSES")

    @property
    def params_schema(self) -> type[BaseModel]:
        return ListProcessesParams

    @property
    def required_capability(self) -> Capability:
        return Capability.SYSTEM_INFO_READ

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

        plan_hash = compute_plan_hash(
            operation=self.name,
            target_files=(),
            target_processes=(),
            parameters=params,
            risk_level=RiskLevel.SAFE,
            summary="List currently running processes",
            consequences="Read-only process inspection.",
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
            summary="List currently running processes",
            consequences="Read-only process inspection.",
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
        return {"operation": self.name, "risk_level": RiskLevel.SAFE.value}

    def execute(self, approved_plan: ApprovedPlan) -> Result:
        adapter = get_platform_adapter()
        limit = approved_plan.plan.parameters.get("limit", 50)
        processes: list[dict[str, Any]] = []

        for proc in psutil.process_iter(["pid", "name", "username", "cpu_percent", "memory_info", "cmdline"]):
            try:
                info = proc.info
                pids = info.get("pid")
                if pids is None:
                    continue
                is_protected = pids in adapter.get_protected_pids()
                is_own = adapter.is_process_owned_by_current_user(pids)
                mem = info.get("memory_info")
                rss = mem.rss if mem else 0
                cmd = " ".join(info.get("cmdline") or [])

                processes.append({
                    "pid": pids,
                    "name": sanitize_text(info.get("name")),
                    "user": sanitize_text(info.get("username")),
                    "cpu_percent": info.get("cpu_percent") or 0.0,
                    "memory_rss_bytes": rss,
                    "cmdline": sanitize_text(cmd[:100]),
                    "is_protected": is_protected,
                    "is_own": is_own,
                })
                if len(processes) >= limit:
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        outcome = TargetOutcome(
            target="processes",
            status=ExecutionStatus.SUCCESS,
            message=f"Retrieved {len(processes)} running processes",
        )
        return Result(
            status=ExecutionStatus.SUCCESS,
            outcomes=[outcome],
            errors=[],
        )


class TerminateProcessParams(BaseModel):
    pids: list[int] = Field(default_factory=list)


class TerminateProcessOperation(BaseOperation):
    """Terminate user-owned processes (DESTRUCTIVE)."""

    def __init__(self) -> None:
        self.adapter = get_platform_adapter()

    @property
    def name(self) -> str:
        return "TERMINATE_PROCESS"

    @property
    def intents(self) -> tuple[str, ...]:
        return ("TERMINATE_PROCESS",)

    @property
    def params_schema(self) -> type[BaseModel]:
        return TerminateProcessParams

    @property
    def required_capability(self) -> Capability:
        return Capability.PROCESS_TERMINATE

    def compute_risk(self, params: dict[str, Any]) -> RiskLevel:
        return RiskLevel.DESTRUCTIVE

    def plan(
        self,
        params: dict[str, Any],
        original_text: str = "",
        allowed_roots: list[Any] | None = None,
    ) -> Plan:
        pids = params.get("pids", [])
        if not pids:
            raise ValueError("No process IDs provided for termination.")

        protected_pids = self.adapter.get_protected_pids()
        target_procs: list[TargetProcess] = []

        for pid in pids:
            if pid in protected_pids:
                raise PermissionError(f"PID {pid} is a protected system process and cannot be terminated.")
            if not self.adapter.is_process_owned_by_current_user(pid):
                raise PermissionError(f"PID {pid} is owned by another user and cannot be terminated.")

            proc_meta = self.adapter.get_process_metadata(pid)
            if proc_meta is None:
                raise ProcessLookupError(f"PID {pid} is no longer running.")
            target_procs.append(proc_meta)

        now = time.time()
        plan_id = f"plan-{uuid.uuid4().hex[:12]}"
        token = str(target_procs[0].pid) if len(target_procs) == 1 else f"KILL {len(target_procs)}"
        summary = f"Terminate process {' '.join(str(p.pid) for p in target_procs)}"
        consequences = "Sending SIGTERM to process. Unsaved progress in the target process may be lost."

        plan_hash = compute_plan_hash(
            operation=self.name,
            target_files=(),
            target_processes=tuple(target_procs),
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
            target_files=(),
            target_processes=tuple(target_procs),
            parameters=params,
            risk_level=RiskLevel.DESTRUCTIVE,
            summary=summary,
            consequences=consequences,
            confirmation_hint=ConfirmationHint(
                kind=ConfirmationKind.TOKEN,
                token=token,
                prompt_message=f"Type '{token}' to confirm termination.",
            ),
            created_at=now,
            expires_at=now + 120.0,
            plan_hash=plan_hash,
        )

    def preview(self, plan: Plan) -> dict[str, Any]:
        return {
            "operation": self.name,
            "pids": [p.pid for p in plan.target_processes],
            "risk_level": RiskLevel.DESTRUCTIVE.value,
            "token": plan.confirmation_hint.token,
        }

    def execute(self, approved_plan: ApprovedPlan) -> Result:
        outcomes: list[TargetOutcome] = []
        errors: list[str] = []

        for target in approved_plan.plan.target_processes:
            try:
                proc = psutil.Process(target.pid)
                # Invariant: Re-verify create_time
                if abs(proc.create_time() - target.create_time) > 0.01:
                    errors.append(f"PID {target.pid} create_time changed (PID reuse detected).")
                    continue
                proc.terminate()
                outcomes.append(
                    TargetOutcome(
                        target=f"PID {target.pid} ({target.name})",
                        status=ExecutionStatus.SUCCESS,
                        message="Sent termination signal.",
                    )
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
                errors.append(f"Could not terminate PID {target.pid}: {exc}")

        status = ExecutionStatus.SUCCESS if not errors else (
            ExecutionStatus.PARTIAL if outcomes else ExecutionStatus.FAILED
        )
        return Result(status=status, outcomes=outcomes, errors=errors)
