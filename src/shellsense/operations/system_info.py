"""System information operations (SAFE, read-only).

Provides memory, CPU, disk, uptime, battery, network, thermal, and platform statistics.
"""

from __future__ import annotations

import os
import time
import uuid
from datetime import UTC, datetime
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
    metric: str = Field(default="all", description="Metric to query: all, memory, cpu, disk, uptime, battery, os, network, temps")
    target: str | None = Field(default=None, description="Optional target drive or mount point")
    per_core: bool = Field(default=False, description="Whether to include per-core CPU breakdown")


class SystemInfoOperation(BaseOperation):
    """System information query operation."""

    @property
    def name(self) -> str:
        return "SYSTEM_INFO"

    @property
    def intents(self) -> tuple[str, ...]:
        return (
            "SHOW_MEMORY",
            "SHOW_CPU",
            "SHOW_DISK",
            "SYSTEM_INFO",
            "SHOW_UPTIME",
            "SHOW_BATTERY",
            "SHOW_OS_INFO",
            "SHOW_NETWORK",
            "SHOW_TEMPERATURES",
        )

    @property
    def params_schema(self) -> type[BaseModel]:
        return SystemInfoParams

    @property
    def required_capability(self) -> Capability:
        return Capability.SYSTEM_INFO_READ

    @property
    def catalog_examples(self) -> tuple[str, ...]:
        return (
            "Show my system usage",
            "Show my RAM usage",
            "Show CPU usage",
            "Show disk usage",
            "How long has my PC been on",
            "Battery level",
            "What OS am I on",
            "My IP address",
            "How hot is my CPU",
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
        expires_at = now + 120.0
        plan_id = f"plan-{uuid.uuid4().hex[:12]}"
        summary = "Query real-time system performance and hardware resource statistics"
        consequences = "Read-only inspection of system hardware metrics. No changes made."

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
        metric = approved_plan.plan.parameters.get("metric", "all").lower()

        # 1. Uptime
        if "uptime" in metric or approved_plan.plan.operation == "SHOW_UPTIME":
            boot_time = psutil.boot_time()
            uptime_seconds = int(time.time() - boot_time)
            days = uptime_seconds // 86400
            hours = (uptime_seconds % 86400) // 3600
            mins = (uptime_seconds % 3600) // 60
            boot_dt = datetime.fromtimestamp(boot_time, tz=UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
            msg = f"System Uptime: {days}d {hours}h {mins}m (Booted on {boot_dt})"
            return Result(
                status=ExecutionStatus.SUCCESS,
                outcomes=[TargetOutcome(target="uptime", status=ExecutionStatus.SUCCESS, message=msg)],
            )

        # 2. Battery
        if "battery" in metric or approved_plan.plan.operation == "SHOW_BATTERY":
            battery = psutil.sensors_battery()
            if battery is None:
                msg = "Battery: No battery detected (Desktop or unsupported hardware)."
            else:
                plugged = "Plugged in (Charging)" if battery.power_plugged else "Running on Battery"
                secs_left = f"{battery.secsleft // 60} minutes remaining" if battery.secsleft > 0 else ""
                msg = f"Battery: {battery.percent}% - {plugged} {secs_left}".strip()
            return Result(
                status=ExecutionStatus.SUCCESS,
                outcomes=[TargetOutcome(target="battery", status=ExecutionStatus.SUCCESS, message=msg)],
            )

        # 3. OS Info
        if "os" in metric or approved_plan.plan.operation == "SHOW_OS_INFO":
            msg = f"Operating System: {os_info.display_name} | Kernel/Release: {os_info.release} | Arch: {os_info.machine}"
            return Result(
                status=ExecutionStatus.SUCCESS,
                outcomes=[TargetOutcome(target="os_info", status=ExecutionStatus.SUCCESS, message=msg)],
            )

        # 4. Network Info (Strictly local interfaces, no remote network calls per Invariant 17)
        if "network" in metric or approved_plan.plan.operation == "SHOW_NETWORK":
            interfaces = psutil.net_if_addrs()
            lines = []
            for iface, addrs in interfaces.items():
                ips = [a.address for a in addrs if a.family.name in {"AF_INET", "AF_INET6"} and not a.address.startswith("127.")]
                if ips:
                    lines.append(f"{iface}: {', '.join(ips)}")
            msg = "Local Network Interfaces: " + (" | ".join(lines) if lines else "No active external local IP detected.")
            return Result(
                status=ExecutionStatus.SUCCESS,
                outcomes=[TargetOutcome(target="network", status=ExecutionStatus.SUCCESS, message=msg)],
            )

        # 5. Temperatures
        if "temp" in metric or approved_plan.plan.operation == "SHOW_TEMPERATURES":
            try:
                temps = psutil.sensors_temperatures() if hasattr(psutil, "sensors_temperatures") else {}
                if temps:
                    readings = []
                    for name, entries in temps.items():
                        for e in entries:
                            readings.append(f"{name} ({e.label or 'temp'}): {e.current}°C")
                    msg = "Hardware Temperatures: " + " | ".join(readings[:6])
                else:
                    msg = "Hardware Temperatures: Sensor data unavailable on this platform/hardware."
            except Exception:
                msg = "Hardware Temperatures: Sensor data unavailable."
            return Result(
                status=ExecutionStatus.SUCCESS,
                outcomes=[TargetOutcome(target="temperatures", status=ExecutionStatus.SUCCESS, message=msg)],
            )

        # 6. Memory
        if "mem" in metric or approved_plan.plan.operation == "SHOW_MEMORY":
            mem = psutil.virtual_memory()
            used_gb = mem.used / (1024**3)
            total_gb = mem.total / (1024**3)
            msg = f"RAM Usage: {used_gb:.1f} GB / {total_gb:.1f} GB ({mem.percent}%)"
            return Result(
                status=ExecutionStatus.SUCCESS,
                outcomes=[TargetOutcome(target="memory", status=ExecutionStatus.SUCCESS, message=msg)],
            )

        # 7. CPU (with per-core support)
        if "cpu" in metric or approved_plan.plan.operation == "SHOW_CPU":
            per_core = approved_plan.plan.parameters.get("per_core", False)
            if per_core:
                cores = psutil.cpu_percent(interval=0.1, percpu=True)
                core_strs = [f"Core {i}: {pct}%" for i, pct in enumerate(cores)]
                msg = f"CPU Per-Core: {', '.join(core_strs)}"
            else:
                cpu_pct = psutil.cpu_percent(interval=0.1)
                msg = f"CPU Usage: {cpu_pct:.1f}% across {psutil.cpu_count(logical=True)} logical cores"
            return Result(
                status=ExecutionStatus.SUCCESS,
                outcomes=[TargetOutcome(target="cpu", status=ExecutionStatus.SUCCESS, message=msg)],
            )

        # 8. Disk (with partition/drive support)
        if "disk" in metric or approved_plan.plan.operation == "SHOW_DISK":
            target_drive = approved_plan.plan.parameters.get("target")
            root_path = target_drive or Path.home().anchor or ("C:\\" if os.name == "nt" else "/")
            try:
                disk = psutil.disk_usage(root_path)
            except Exception:
                disk = psutil.disk_usage("/")
                root_path = "/"
            used_gb = disk.used / (1024**3)
            total_gb = disk.total / (1024**3)
            free_gb = disk.free / (1024**3)
            msg = f"Disk Usage ({root_path}): {used_gb:.1f} GB / {total_gb:.1f} GB ({disk.percent}% used, {free_gb:.1f} GB free)"
            return Result(
                status=ExecutionStatus.SUCCESS,
                outcomes=[TargetOutcome(target="disk", status=ExecutionStatus.SUCCESS, message=msg)],
            )

        # 9. All / Overall System Info
        mem = psutil.virtual_memory()
        cpu_pct = psutil.cpu_percent(interval=0.1)
        root_path = Path.home().anchor or ("C:\\" if os.name == "nt" else "/")
        try:
            disk = psutil.disk_usage(root_path)
        except Exception:
            disk = psutil.disk_usage("/")
        msg = f"System: {os_info.display_name} | CPU: {cpu_pct:.1f}% | RAM: {mem.percent}% | Disk: {disk.percent}%"
        return Result(
            status=ExecutionStatus.SUCCESS,
            outcomes=[TargetOutcome(target="system", status=ExecutionStatus.SUCCESS, message=msg)],
        )
