"""System information operations (SAFE, read-only).

Provides memory, CPU, disk, and platform statistics.
"""

from __future__ import annotations

import os
import time
import uuid
from pathlib import Path
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
    compute_plan_hash,
)
from shellsense.operations.registry import BaseOperation
from shellsense.platform import get_platform_adapter


class SystemInfoParams(BaseModel):
    """Parameters for system info queries."""
    metric: str = Field(default="all", description="Metric to query: all, memory, cpu, disk")


class SystemInfoOperation(BaseOperation):
    """System information query operation."""

    @property
    def name(self) -> str:
        return "SYSTEM_INFO"

    @property
    def intents(self) -> tuple[str, ...]:
        return ("SHOW_MEMORY", "SHOW_CPU", "SHOW_DISK", "SYSTEM_INFO")

    @property
    def params_schema(self) -> type[BaseModel]:
        return SystemInfoParams

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
        expires_at = now + 120.0
        plan_id = f"plan-{uuid.uuid4().hex[:12]}"
        summary = "Query real-time system performance and hardware resource statistics"
        consequences = "Read-only inspection of memory, CPU, and disk metrics. No changes made."

        plan_hash = compute_plan_hash(
            operation=self.name,
            target_files=(),
            target_processes=(),
            parameters=params,
            risk_level=RiskLevel.SAFE,
            summary=summary,
            consequences=consequences,
            created_at=now,
            expires_at=expires_at,
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
                prompt_message="Read-only SAFE operation automatically approved.",
            ),
            created_at=now,
            expires_at=expires_at,
            plan_hash=plan_hash,
        )

    def preview(self, plan: Plan) -> dict[str, Any]:
        return {
            "operation": self.name,
            "risk_level": RiskLevel.SAFE.value,
            "summary": plan.summary,
            "metric": plan.parameters.get("metric", "all"),
        }

    def execute(self, approved_plan: ApprovedPlan) -> Result:
        adapter = get_platform_adapter()
        os_info = adapter.get_os_info()

        # Gather psutil stats
        mem = psutil.virtual_memory()
        cpu_pct = psutil.cpu_percent(interval=0.1)
        root_path = Path.home().anchor or ("C:\\" if os.name == "nt" else "/")
        try:
            disk = psutil.disk_usage(root_path)
        except Exception:
            disk = psutil.disk_usage("/")

        {
            "os": os_info.display_name,
            "cpu_percent": cpu_pct,
            "cpu_count": psutil.cpu_count(logical=True),
            "ram_total_bytes": mem.total,
            "ram_used_bytes": mem.used,
            "ram_free_bytes": mem.free,
            "ram_percent": mem.percent,
            "disk_total_bytes": disk.total,
            "disk_used_bytes": disk.used,
            "disk_free_bytes": disk.free,
            "disk_percent": disk.percent,
        }

        # Build message summary
        metric = approved_plan.plan.parameters.get("metric", "all").lower()
        if "mem" in metric or approved_plan.plan.operation == "SHOW_MEMORY":
            used_gb = mem.used / (1024**3)
            total_gb = mem.total / (1024**3)
            msg = f"RAM Usage: {used_gb:.1f} GB / {total_gb:.1f} GB ({mem.percent}%)"
        elif "cpu" in metric or approved_plan.plan.operation == "SHOW_CPU":
            msg = f"CPU Usage: {cpu_pct:.1f}% across {psutil.cpu_count()} cores"
        elif "disk" in metric or approved_plan.plan.operation == "SHOW_DISK":
            used_gb = disk.used / (1024**3)
            total_gb = disk.total / (1024**3)
            msg = f"Disk Usage: {used_gb:.1f} GB / {total_gb:.1f} GB ({disk.percent}%)"
        else:
            msg = f"System: {os_info.display_name} | CPU: {cpu_pct:.1f}% | RAM: {mem.percent}% | Disk: {disk.percent}%"

        outcome = TargetOutcome(
            target="system",
            status=ExecutionStatus.SUCCESS,
            message=msg,
        )

        return Result(
            status=ExecutionStatus.SUCCESS,
            outcomes=[outcome],
            errors=[],
        )
