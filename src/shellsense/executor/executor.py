"""The sole execution gate for ShellSense.

Invariant 6: The executor accepts ONLY an ApprovedPlan. It re-verifies the plan hash
and re-checks every target immediately before acting. There is no other code path that performs side effects.
"""

from __future__ import annotations

import contextlib
import time
from typing import Any

from shellsense.models import (
    ApprovedPlan,
    ExecutionStatus,
    Result,
    RiskLevel,
)
from shellsense.operations import GLOBAL_REGISTRY
from shellsense.platform import get_platform_adapter
from shellsense.safety.consent import PermissionGate
from shellsense.storage.audit import DEFAULT_AUDIT_LOGGER, AuditDecision, AuditLogger
from shellsense.storage.history import DEFAULT_HISTORY_STORE, HistoryStore


class Executor:
    """The sole side-effect execution gate enforcing strict re-verification."""

    def __init__(
        self,
        permission_gate: PermissionGate | None = None,
        audit_logger: AuditLogger | None = None,
        history_store: HistoryStore | None = None,
    ) -> None:
        self.permission_gate = permission_gate or PermissionGate()
        self.audit_logger = audit_logger or DEFAULT_AUDIT_LOGGER
        self.history_store = history_store or DEFAULT_HISTORY_STORE
        self.adapter = get_platform_adapter()

    def execute(self, approved_plan: ApprovedPlan, session_id: str = "default") -> Result:
        """Execute an approved plan with full re-verification.

        Strict Steps:
        1. Invariant 6: Re-verify plan hash.
        2. Verify expiry timestamp.
        3. Re-verify capability grant via PermissionGate.
        4. TOCTOU: Re-verify every target file metadata (inode, dev, size, mtime).
        5. TOCTOU: Re-verify every target process (PID + create_time).
        6. Dispatch to registered operation.
        7. Audit-log and record in history.
        """
        plan = approved_plan.plan

        # 1. Re-verify plan hash
        if not plan.verify_hash():
            self._log_and_record(
                session_id=session_id,
                plan=plan,
                decision=AuditDecision.FAILED,
                status=ExecutionStatus.FAILED,
                errors=["Plan hash re-verification failed before execution."],
            )
            return Result(
                status=ExecutionStatus.FAILED,
                errors=["Security Error: Plan hash re-verification failed immediately before execution."],
            )

        # 2. Re-verify expiry
        if time.time() > plan.expires_at:
            self._log_and_record(
                session_id=session_id,
                plan=plan,
                decision=AuditDecision.FAILED,
                status=ExecutionStatus.FAILED,
                errors=["Plan expired prior to execution."],
            )
            return Result(
                status=ExecutionStatus.FAILED,
                errors=[f"Security Error: Plan '{plan.plan_id}' expired before execution."],
            )

        # 3. Lookup operation from registry
        op = GLOBAL_REGISTRY.get_by_name(plan.operation)
        if op is None:
            self._log_and_record(
                session_id=session_id,
                plan=plan,
                decision=AuditDecision.REFUSED,
                status=ExecutionStatus.FAILED,
                errors=[f"Unknown operation '{plan.operation}'."],
            )
            return Result(
                status=ExecutionStatus.FAILED,
                errors=[f"Security Error: Unknown operation '{plan.operation}' refused."],
            )

        # 4. Re-verify capability grant (in case of mid-flight revocation)
        if not self.permission_gate.has_capability(op.required_capability):
            self._log_and_record(
                session_id=session_id,
                plan=plan,
                decision=AuditDecision.REFUSED,
                status=ExecutionStatus.FAILED,
                errors=[f"Capability '{op.required_capability.value}' not granted."],
            )
            return Result(
                status=ExecutionStatus.FAILED,
                errors=[f"Security Error: Required capability '{op.required_capability.value}' is not granted."],
            )

        # 5. TOCTOU target files re-verification
        for target_file in plan.target_files:
            if not self.adapter.verify_target_file_unchanged(target_file):
                err = f"TOCTOU violation: Target file '{target_file.path}' changed on disk after plan generation."
                self._log_and_record(
                    session_id=session_id,
                    plan=plan,
                    decision=AuditDecision.FAILED,
                    status=ExecutionStatus.FAILED,
                    errors=[err],
                )
                return Result(
                    status=ExecutionStatus.FAILED,
                    errors=[err],
                )

        # 6. TOCTOU target processes re-verification
        for target_proc in plan.target_processes:
            if not self.adapter.verify_target_process_unchanged(target_proc):
                err = f"TOCTOU violation: Target PID {target_proc.pid} was recycled or terminated after plan generation."
                self._log_and_record(
                    session_id=session_id,
                    plan=plan,
                    decision=AuditDecision.FAILED,
                    status=ExecutionStatus.FAILED,
                    errors=[err],
                )
                return Result(
                    status=ExecutionStatus.FAILED,
                    errors=[err],
                )

        # 7. Execute the operation
        try:
            result = op.execute(approved_plan)
        except Exception as exc:
            err = f"Operation execution failed with exception: {exc}"
            self._log_and_record(
                session_id=session_id,
                plan=plan,
                decision=AuditDecision.FAILED,
                status=ExecutionStatus.FAILED,
                errors=[err],
            )
            return Result(
                status=ExecutionStatus.FAILED,
                errors=[err],
            )

        # 8. Record successful or partial decision
        decision = (
            AuditDecision.AUTO_ALLOWED
            if plan.risk_level == RiskLevel.SAFE
            else AuditDecision.APPROVED
        )
        self._log_and_record(
            session_id=session_id,
            plan=plan,
            decision=decision,
            status=result.status,
            errors=result.errors,
            undo_data=None,
        )

        return result

    def _log_and_record(
        self,
        session_id: str,
        plan: Any,
        decision: AuditDecision,
        status: ExecutionStatus,
        errors: list[str],
        undo_data: dict[str, Any] | None = None,
    ) -> None:
        """Write audit log entry and record in SQLite history."""
        # 1. Audit log write (mandatory; aborts if non-SAFE write fails)
        self.audit_logger.log(
            session_id=session_id,
            original_text="",
            intent=plan.operation,
            plan_hash=plan.plan_hash,
            risk=plan.risk_level,
            decision=decision,
            result_status=status.value,
            errors=errors,
        )

        # 2. SQLite history write (isolated from audit failure)
        with contextlib.suppress(Exception):
            self.history_store.record_execution(
                operation=plan.operation,
                summary=plan.summary,
                risk_level=plan.risk_level.value,
                plan_id=plan.plan_id,
                plan_hash=plan.plan_hash,
                status=status.value,
                original_text="",
                undo_data=undo_data,
            )


DEFAULT_EXECUTOR = Executor()
