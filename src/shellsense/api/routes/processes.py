"""Process listing and termination planning routes."""

from __future__ import annotations

from typing import Any

import psutil
from fastapi import APIRouter, HTTPException, status

from shellsense.api.schemas import ProcessPlanRequest
from shellsense.models import Intent
from shellsense.planner import DEFAULT_PLANNER
from shellsense.platform import get_platform_adapter
from shellsense.safety.approval import DEFAULT_PLAN_STORE
from shellsense.safety.sanitize import sanitize_text

router = APIRouter(prefix="/processes", tags=["processes"])


@router.get("")
async def list_processes(limit: int = 100) -> dict[str, Any]:
    adapter = get_platform_adapter()
    protected_pids = adapter.get_protected_pids()
    results = []

    for proc in psutil.process_iter(["pid", "name", "username", "cpu_percent", "memory_info"]):
        try:
            info = proc.info
            pid = info.get("pid")
            if pid is None:
                continue
            is_protected = pid in protected_pids
            is_own = adapter.is_process_owned_by_current_user(pid)
            mem = info.get("memory_info")
            rss = mem.rss if mem else 0

            results.append({
                "pid": pid,
                "name": sanitize_text(info.get("name")),
                "user": sanitize_text(info.get("username")),
                "cpu_percent": info.get("cpu_percent") or 0.0,
                "memory_rss_bytes": rss,
                "is_protected": is_protected,
                "is_own": is_own,
                "can_terminate": (not is_protected) and is_own,
            })
            if len(results) >= limit:
                break
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    return {"processes": results}


@router.post("/plan")
async def create_process_plan(req: ProcessPlanRequest) -> dict[str, Any]:
    """Create a Plan to terminate process(es). Does NOT terminate by itself."""
    if req.action.lower() != "terminate":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported process action.")

    intent = Intent(
        operation="TERMINATE_PROCESS",
        params={"pids": req.pids},
        confidence=1.0,
        original_text=f"UI terminate process {req.pids}",
    )
    try:
        plan = DEFAULT_PLANNER.create_plan(intent)
        DEFAULT_PLAN_STORE.store_plan(plan)
        return {
            "plan_id": plan.plan_id,
            "plan_hash": plan.plan_hash,
            "risk": plan.risk_level.value,
            "summary": plan.summary,
            "consequences": plan.consequences,
            "confirmation_token": plan.confirmation_hint.token,
        }
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
