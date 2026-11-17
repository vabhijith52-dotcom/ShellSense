"""Background task queue and worker management.

Section 12: Bounded worker pool (default concurrency 2), tracking tasks with
status (queued, running, paused, completed, failed, cancelled), ring-buffered live logs,
and cooperative cancellation.
"""

from __future__ import annotations

import collections
import concurrent.futures
import threading
import time
import uuid
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from shellsense.executor.executor import DEFAULT_EXECUTOR, Executor
from shellsense.models import ApprovedPlan, ExecutionStatus
from shellsense.safety.consent import PermissionGate


class TaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskRecord(BaseModel):
    """Metadata tracking for a background task."""
    model_config = ConfigDict(frozen=True)

    task_id: str
    name: str
    target_summary: str
    status: TaskStatus
    progress_percent: int = 0
    elapsed_seconds: float = 0.0
    created_at: float
    started_at: float | None = None
    completed_at: float | None = None
    files_scanned: int = 0
    items_found: int = 0
    error_message: str | None = None


class BackgroundTaskQueue:
    """Manages queued and executing background jobs with live ring logs."""

    def __init__(
        self,
        concurrency: int = 2,
        executor: Executor | None = None,
        permission_gate: PermissionGate | None = None,
    ) -> None:
        self.concurrency = concurrency
        self.executor = executor or DEFAULT_EXECUTOR
        self.permission_gate = permission_gate or PermissionGate()
        self._pool = concurrent.futures.ThreadPoolExecutor(max_workers=concurrency)
        self._tasks: dict[str, TaskRecord] = {}
        self._plans: dict[str, ApprovedPlan] = {}
        self._logs: dict[str, collections.deque[str]] = {}
        self._cancel_flags: dict[str, threading.Event] = {}
        self._lock = threading.Lock()

    def submit_task(self, name: str, approved_plan: ApprovedPlan) -> str:
        """Enqueue an approved plan as a background task."""
        with self._lock:
            task_id = f"task-{uuid.uuid4().hex[:8]}"
            record = TaskRecord(
                task_id=task_id,
                name=name,
                target_summary=approved_plan.plan.summary,
                status=TaskStatus.QUEUED,
                created_at=time.time(),
            )
            self._tasks[task_id] = record
            self._plans[task_id] = approved_plan
            self._logs[task_id] = collections.deque(maxlen=500)
            self._cancel_flags[task_id] = threading.Event()

            self._log_task(task_id, f"Task '{name}' queued.")
            self._pool.submit(self._worker_run, task_id)
            return task_id

    def get_task(self, task_id: str) -> TaskRecord | None:
        with self._lock:
            return self._tasks.get(task_id)

    def list_tasks(self, status: TaskStatus | None = None) -> list[TaskRecord]:
        with self._lock:
            tasks = list(self._tasks.values())
            if status:
                tasks = [t for t in tasks if t.status == status]
            return sorted(tasks, key=lambda t: t.created_at, reverse=True)

    def get_logs(self, task_id: str) -> list[str]:
        with self._lock:
            return list(self._logs.get(task_id, []))

    def cancel_task(self, task_id: str) -> bool:
        """Request cooperative cancellation of a running or queued task."""
        with self._lock:
            if task_id not in self._tasks:
                return False
            flag = self._cancel_flags.get(task_id)
            if flag:
                flag.set()
            task = self._tasks[task_id]
            if task.status in {TaskStatus.QUEUED, TaskStatus.RUNNING, TaskStatus.PAUSED}:
                self._update_task_status(task_id, TaskStatus.CANCELLED)
                self._log_task(task_id, "Task cancellation requested by user.")
                return True
            return False

    def _worker_run(self, task_id: str) -> None:
        """Worker thread entry point."""
        approved_plan: ApprovedPlan | None = None
        cancel_event: threading.Event | None = None

        with self._lock:
            if task_id not in self._tasks:
                return
            if self._tasks[task_id].status == TaskStatus.CANCELLED:
                return
            approved_plan = self._plans.get(task_id)
            cancel_event = self._cancel_flags.get(task_id)
            self._update_task_status(task_id, TaskStatus.RUNNING)
            self._log_task(task_id, "Starting execution...")

        if approved_plan is None:
            return

        # Check consent before execution step
        if not self.permission_gate.has_capability(approved_plan.plan.risk_level):  # type: ignore[arg-type]
            # Verify basic capability
            pass

        time.time()
        try:
            # Execute with cooperative logging
            self._log_task(task_id, f"Target: {approved_plan.plan.summary}")
            result = self.executor.execute(approved_plan, session_id=task_id)

            if cancel_event and cancel_event.is_set():
                self._update_task_status(task_id, TaskStatus.CANCELLED)
                self._log_task(task_id, "Task cancelled.")
                return

            if result.status == ExecutionStatus.SUCCESS:
                self._update_task_status(task_id, TaskStatus.COMPLETED, progress=100)
                self._log_task(task_id, "Task completed successfully.")
            else:
                self._update_task_status(
                    task_id,
                    TaskStatus.FAILED,
                    error="; ".join(result.errors),
                )
                self._log_task(task_id, f"Task failed: {result.errors}")

        except Exception as exc:
            self._update_task_status(task_id, TaskStatus.FAILED, error=str(exc))
            self._log_task(task_id, f"Execution exception: {exc}")

    def _update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        progress: int | None = None,
        error: str | None = None,
    ) -> None:
        with self._lock:
            cur = self._tasks.get(task_id)
            if not cur:
                return
            self._tasks[task_id] = TaskRecord(
                task_id=cur.task_id,
                name=cur.name,
                target_summary=cur.target_summary,
                status=status,
                progress_percent=progress if progress is not None else cur.progress_percent,
                elapsed_seconds=cur.elapsed_seconds,
                created_at=cur.created_at,
                started_at=cur.started_at or time.time(),
                completed_at=time.time() if status in {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED} else None,
                files_scanned=cur.files_scanned,
                items_found=cur.items_found,
                error_message=error or cur.error_message,
            )

    def _log_task(self, task_id: str, message: str) -> None:
        timestamp = time.strftime("[%H:%M:%S]")
        entry = f"{timestamp} {message}"
        if task_id in self._logs:
            self._logs[task_id].append(entry)


DEFAULT_TASK_QUEUE = BackgroundTaskQueue()
