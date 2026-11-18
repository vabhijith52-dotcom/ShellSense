"""Plan inspection and approval endpoints.

Invariant 6 & 7: POST /plans/{id}/approve is the ONLY endpoint executing side-effects.
The client can never send targets or parameters in an approval.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

from shellsense.api.schemas import ApprovePlanRequest, ResultMessage
from shellsense.executor.executor import DEFAULT_EXECUTOR
from shellsense.safety.approval import DEFAULT_PLAN_STORE

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("/{plan_id}")
async def get_plan(plan_id: str) -> dict[str, Any]:
    plan = DEFAULT_PLAN_STORE.get_plan(plan_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan '{plan_id}' not found or has expired.",
        )
    return {
        "plan_id": plan.plan_id,
        "operation": plan.operation,
        "risk_level": plan.risk_level.value,
        "summary": plan.summary,
        "consequences": plan.consequences,
        "created_at": plan.created_at,
        "expires_at": plan.expires_at,
        "plan_hash": plan.plan_hash,
    }


@router.post("/{plan_id}/approve", response_model=ResultMessage)
async def approve_plan(plan_id: str, req: ApprovePlanRequest) -> ResultMessage:
    """Approve a plan and dispatch to the Executor."""
    try:
        approved_plan = DEFAULT_PLAN_STORE.approve_plan(
            plan_id=plan_id,
            provided_hash=req.plan_hash,
            confirmation_input=req.confirmation_input,
        )
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found.")
    except TimeoutError as te:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(te))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))

    # Execute via sole gate
    result = DEFAULT_EXECUTOR.execute(approved_plan)
    summary_msg = result.outcomes[0].message if result.outcomes else "Execution complete"
    return ResultMessage(
        status=result.status.value,
        summary=summary_msg,
        errors=result.errors,
    )


@router.post("/{plan_id}/deny")
async def deny_plan(plan_id: str) -> dict[str, Any]:
    if DEFAULT_PLAN_STORE.deny_plan(plan_id):
        return {"status": "denied", "plan_id": plan_id}
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found.")
