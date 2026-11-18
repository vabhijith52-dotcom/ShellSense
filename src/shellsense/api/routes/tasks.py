"""Background task routes."""

from __future__ import annotations

import contextlib
from typing import Any

from fastapi import APIRouter, HTTPException, status

from shellsense.executor.jobs import DEFAULT_TASK_QUEUE, TaskStatus

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("")
async def list_tasks(status_filter: str | None = None) -> dict[str, Any]:
    filter_val = None
    if status_filter:
        with contextlib.suppress(ValueError):
            filter_val = TaskStatus(status_filter.lower())
    tasks = DEFAULT_TASK_QUEUE.list_tasks(status=filter_val)
    return {"tasks": [t.model_dump() for t in tasks]}


@router.get("/{task_id}")
async def get_task(task_id: str) -> dict[str, Any]:
    task = DEFAULT_TASK_QUEUE.get_task(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
    logs = DEFAULT_TASK_QUEUE.get_logs(task_id)
    return {
        "task": task.model_dump(),
        "logs": logs,
    }


@router.post("/{task_id}/cancel")
async def cancel_task(task_id: str) -> dict[str, Any]:
    if DEFAULT_TASK_QUEUE.cancel_task(task_id):
        return {"status": "cancelled", "task_id": task_id}
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not cancel task.")
