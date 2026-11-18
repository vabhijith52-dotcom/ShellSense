"""Permissions inspection, wizard grant, and revocation endpoints."""

from __future__ import annotations

import contextlib
from typing import Any

from fastapi import APIRouter, HTTPException, status

from shellsense.api.schemas import GrantPermissionRequest
from shellsense.models import Capability
from shellsense.safety.consent import PermissionGate

router = APIRouter(prefix="/permissions", tags=["permissions"])
gate = PermissionGate()


@router.get("")
async def get_permissions() -> dict[str, Any]:
    is_locked = gate.is_locked()
    grant = gate.get_current_grant()
    return {
        "is_locked": is_locked,
        "capabilities": [c.value for c in (grant.capabilities if grant else [])],
        "folder_roots": grant.folder_roots if grant else [],
        "created_at": grant.created_at if grant else None,
        "expires_at": grant.expires_at if grant else None,
    }


@router.post("/grant")
async def grant_permissions(req: GrantPermissionRequest) -> dict[str, Any]:
    """GUI first-run wizard submission.

    Requires live human typed phrase 'I GRANT ACCESS'.
    """
    if req.confirmation_phrase != "I GRANT ACCESS":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation phrase mismatch. Must type 'I GRANT ACCESS'.",
        )

    valid_caps = []
    for c_str in req.capabilities:
        with contextlib.suppress(ValueError):
            valid_caps.append(Capability(c_str))

    try:
        # force_tty_check=False here because this is the GUI wizard endpoint
        gate.write_grant(
            capabilities=valid_caps,
            folder_roots=req.folder_roots,
            force_tty_check=False,
        )
        return {"status": "granted"}
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.post("/revoke")
async def revoke_permissions() -> dict[str, Any]:
    gate.revoke()
    return {"status": "revoked", "is_locked": True}
