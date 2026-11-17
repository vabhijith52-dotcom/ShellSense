"""History and undo planning endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from shellsense.storage.history import DEFAULT_HISTORY_STORE

router = APIRouter(prefix="/history", tags=["history"])


@router.get("")
async def get_history(
    limit: int = 50,
    offset: int = 0,
    op_type: str | None = None,
    range_days: int | None = None,
):
    items = DEFAULT_HISTORY_STORE.get_history(
        limit=limit,
        offset=offset,
        op_type=op_type,
        range_days=range_days,
    )
    return {"history": items}


@router.get("/{record_id}")
async def get_history_detail(record_id: int):
    item = DEFAULT_HISTORY_STORE.get_history_item(record_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="History record not found.")
    return {"item": item}
