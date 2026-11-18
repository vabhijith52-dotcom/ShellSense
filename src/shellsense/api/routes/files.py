"""File listing and planning routes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, status

from shellsense.api.schemas import FilePlanRequest
from shellsense.models import Intent
from shellsense.planner import DEFAULT_PLANNER
from shellsense.safety.approval import DEFAULT_PLAN_STORE
from shellsense.safety.consent import PermissionGate
from shellsense.safety.path_guard import PathGuard

router = APIRouter(prefix="/files", tags=["files"])
gate = PermissionGate()
guard = PathGuard()


@router.get("")
async def list_files(path: str = "") -> dict[str, Any]:
    """List directory contents within granted roots."""
    roots = gate.get_granted_roots()
    if not roots:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Zero folder roots granted. ShellSense is locked. Please configure permissions.",
        )

    target_dir = Path(path).expanduser().resolve() if path else roots[0]
    safe, reason = guard.validate_path(target_dir, allowed_roots=roots)
    if not safe:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access forbidden: {reason}",
        )

    if not target_dir.exists() or not target_dir.is_dir():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Directory '{target_dir}' not found.",
        )

    entries = []
    for item in target_dir.iterdir():
        try:
            st = item.stat()
            entries.append({
                "name": item.name,
                "path": str(item.resolve()),
                "is_dir": item.is_dir(),
                "size_bytes": st.st_size if not item.is_dir() else 0,
                "mtime": st.st_mtime,
            })
        except (PermissionError, OSError):
            pass

    return {
        "current_path": str(target_dir),
        "granted_roots": [str(r) for r in roots],
        "entries": sorted(entries, key=lambda x: (not x["is_dir"], x["name"].lower())),
    }


@router.post("/plan")
async def create_file_plan(req: FilePlanRequest) -> dict[str, Any]:
    """Create a Plan for a file action (e.g. DELETE, MOVE, RENAME). Does NOT execute."""
    action_map = {
        "delete": "TRASH_FILES",
        "move": "MOVE",
        "copy": "COPY",
        "rename": "RENAME",
        "new_folder": "CREATE_FOLDER",
    }
    op_name = action_map.get(req.action.lower())
    if not op_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported file action.")

    intent = Intent(
        operation=op_name,
        params={"targets": req.sources, "destination": req.destination},
        confidence=1.0,
        original_text=f"UI action {req.action}",
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
            "target_count": len(plan.target_files),
        }
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
