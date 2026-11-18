"""Process operations (list, inspect, search, port lookup, terminate).

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
    sort_by: str = Field(default="cpu")  # "cpu" | "memory"
    name: str | None = Field(default=None)
    port: int | None = Field(default=None)


class ListProcessesOperation(BaseOperation):
    """List and search running processes (SAFE, read-only)."""

    @property
    def name(self) -> str:
        return "LIST_PROCESSES"

    @property
    def intents(self) -> tuple[str, ...]:
        return ("LIST_PROCESSES", "TOP_PROCESSES", "FIND_PROCESS", "PROCESS_BY_PORT")

    @property
    def params_schema(self) -> type[BaseModel]:
        return ListProcessesParams

    @property
    def required_capability(self) -> Capability:
        return Capability.SYSTEM_INFO_READ

    @property
    def catalog_examples(self) -> tuple[str, ...]:
        return (
            "List running processes",
            "Top processes",
            "Top 5 processes using the most RAM",
            "Is Chrome running",
            "What's using port 8080",
        )

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
        summary = "Inspect running processes or query port usage"
        consequences = "Read-only process inspection."

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
        params = approved_plan.plan.parameters
        port = params.get("port")
        search_name = params.get("name")
        sort_by = params.get("sort_by", "cpu").lower()
        limit = params.get("limit", 50)

        # 1. PROCESS_BY_PORT
        if port is not None or approved_plan.plan.operation == "PROCESS_BY_PORT":
            port_val = int(port or 0)
            matching_procs: list[str] = []
            try:
                for conn in psutil.net_connections(kind="inet"):
                    if conn.laddr and conn.laddr.port == port_val and conn.pid:
                        try:
                            proc = psutil.Process(conn.pid)
                            is_own = adapter.is_process_owned_by_current_user(conn.pid)
                            ownership_note = "user-owned" if is_own else "system/other user"
                            matching_procs.append(f"PID {conn.pid} ({proc.name()}, {ownership_note})")
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            matching_procs.append(f"PID {conn.pid} (access restricted)")
            except Exception as e:
                return Result(
                    status=ExecutionStatus.FAILED,
                    errors=[f"Unable to inspect network connections: {e}"],
                )

            if matching_procs:
                msg = f"Port {port_val} is in use by: {', '.join(matching_procs)}"
            else:
                msg = f"No active user-accessible process found listening on port {port_val}."
            return Result(
                status=ExecutionStatus.SUCCESS,
                outcomes=[TargetOutcome(target=f"port_{port_val}", status=ExecutionStatus.SUCCESS, message=msg)],
            )

        # 2. FIND_PROCESS by name
        if search_name or approved_plan.plan.operation == "FIND_PROCESS":
            name_lower = str(search_name or "").lower().strip()
            found: list[str] = []
            for proc in psutil.process_iter(["pid", "name", "username"]):
                try:
                    pname = str(proc.info.get("name") or "").lower()
                    if name_lower in pname:
                        pid = proc.info.get("pid")
                        found.append(f"{proc.info.get('name')} (PID {pid})")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            if found:
                msg = f"Process '{name_lower}' is active: {', '.join(found[:10])}"
            else:
                msg = f"No running process matching '{name_lower}' was found."
            return Result(
                status=ExecutionStatus.SUCCESS,
                outcomes=[TargetOutcome(target="process_search", status=ExecutionStatus.SUCCESS, message=msg)],
            )

        # 3. LIST_PROCESSES / TOP_PROCESSES
        processes: list[dict[str, Any]] = []
        for proc in psutil.process_iter(["pid", "name", "username", "cpu_percent", "memory_info", "cmdline"]):
            try:
                info = proc.info
                pids = info.get("pid")
                if pids is None:
                    continue
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
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        if sort_by == "memory":
            processes.sort(key=lambda x: x["memory_rss_bytes"], reverse=True)
        else:
            processes.sort(key=lambda x: x["cpu_percent"], reverse=True)

        sliced = processes[:limit]
        sample_str = ", ".join(f"{p['name']} (PID {p['pid']})" for p in sliced[:5])
        msg = f"Found {len(processes)} processes (showing top {len(sliced)}): {sample_str}"

        return Result(
            status=ExecutionStatus.SUCCESS,
            outcomes=[TargetOutcome(target="processes", status=ExecutionStatus.SUCCESS, message=msg)],
        )


class TerminateProcessParams(BaseModel):
    pids: list[int] = Field(default_factory=list)
    process_name: str | None = None


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

    @property
    def catalog_examples(self) -> tuple[str, ...]:
        return (
            "Kill process 1234",
            "Terminate PID 4567",
            "Kill Chrome",
            "Stop all python processes",
        )

    def compute_risk(self, params: dict[str, Any]) -> RiskLevel:
        return RiskLevel.DESTRUCTIVE

    def plan(
        self,
        params: dict[str, Any],
        original_text: str = "",
        allowed_roots: list[Any] | None = None,
    ) -> Plan:
        pids = list(params.get("pids", []))
        process_name = params.get("process_name")

        # Resolve process_name to user-owned PIDs if given
        if not pids and process_name:
            pname_lower = str(process_name).lower()
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    pname = str(proc.info.get("name") or "").lower()
                    pid = proc.info.get("pid")
                    if pid and pname_lower in pname and self.adapter.is_process_owned_by_current_user(pid):
                        pids.append(pid)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

        if not pids:
            raise ValueError(f"No active user-owned processes found to terminate matching {params}.")

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
