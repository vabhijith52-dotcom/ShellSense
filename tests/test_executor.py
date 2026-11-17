"""Tests for executor re-verification, TOCTOU checks, and plan integrity."""

import time
from pathlib import Path

from shellsense.executor.executor import Executor
from shellsense.models import (
    ApprovedPlan,
    Capability,
    ConfirmationHint,
    ConfirmationKind,
    ExecutionStatus,
    Plan,
    RiskLevel,
    compute_plan_hash,
)
from shellsense.safety.approval import PlanStore
from shellsense.safety.consent import PermissionGate
from shellsense.storage.audit import AuditLogger
from shellsense.storage.history import HistoryStore


def test_executor_with_tampered_plan_fails(tmp_path: Path) -> None:
    gate = PermissionGate(config_dir=tmp_path / "config")
    gate.write_grant([Capability.SYSTEM_INFO_READ], [], force_tty_check=False)

    audit = AuditLogger(log_dir=tmp_path / "logs")
    history = HistoryStore(db_path=tmp_path / "history.sqlite3")
    executor = Executor(permission_gate=gate, audit_logger=audit, history_store=history)

    # Valid plan
    now = time.time()
    plan_hash = compute_plan_hash(
        operation="SYSTEM_INFO",
        target_files=(),
        target_processes=(),
        parameters={},
        risk_level=RiskLevel.SAFE,
        summary="Info",
        consequences="Read-only",
        created_at=now,
        expires_at=now + 120.0,
    )
    plan = Plan(
        plan_id="p-1",
        operation="SYSTEM_INFO",
        parameters={},
        risk_level=RiskLevel.SAFE,
        summary="Info",
        consequences="Read-only",
        confirmation_hint=ConfirmationHint(kind=ConfirmationKind.NONE, prompt_message=""),
        created_at=now,
        expires_at=now + 120.0,
        plan_hash=plan_hash,
    )

    store = PlanStore()
    store.store_plan(plan)
    store.approve_plan("p-1", plan_hash)

    # Corrupt the plan inside approved plan by replacing with tampered parameters
    corrupted_plan = Plan(
        plan_id=plan.plan_id,
        operation=plan.operation,
        parameters={"injected": "malicious"},
        risk_level=plan.risk_level,
        summary=plan.summary,
        consequences=plan.consequences,
        confirmation_hint=plan.confirmation_hint,
        created_at=plan.created_at,
        expires_at=plan.expires_at,
        plan_hash=plan.plan_hash,
    )
    # Re-wrap in approved
    from shellsense.models import _APPROVED_PLAN_SENTINEL

    corrupted_approved = ApprovedPlan(
        plan=corrupted_plan,
        approved_at=now,
        _sentinel=_APPROVED_PLAN_SENTINEL,
    )

    # Executor must catch tampering and fail
    res = executor.execute(corrupted_approved)
    assert res.status == ExecutionStatus.FAILED
    assert "Plan hash re-verification failed" in res.errors[0]
