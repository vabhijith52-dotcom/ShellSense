"""Tests for plan storage, expiry, single-use approval, and replay protection."""

import time

import pytest

from shellsense.models import (
    ConfirmationHint,
    ConfirmationKind,
    Plan,
    RiskLevel,
    TargetFile,
    compute_plan_hash,
)
from shellsense.safety.approval import PlanStore


def make_test_plan(
    plan_id: str,
    risk_level: RiskLevel = RiskLevel.MODIFY,
    token: str | None = None,
    expires_in: float = 120.0,
) -> Plan:
    now = time.time()
    expires_at = now + expires_in
    target = TargetFile(path="/test/path", exists=True)
    plan_hash = compute_plan_hash(
        operation="MOVE",
        target_files=(target,),
        target_processes=(),
        parameters={},
        risk_level=risk_level,
        summary="Test Plan",
        consequences="Test consequences",
        created_at=now,
        expires_at=expires_at,
    )
    return Plan(
        plan_id=plan_id,
        operation="MOVE",
        target_files=(target,),
        target_processes=(),
        parameters={},
        risk_level=risk_level,
        summary="Test Plan",
        consequences="Test consequences",
        confirmation_hint=ConfirmationHint(
            kind=ConfirmationKind.TOKEN if token else ConfirmationKind.BUTTON,
            token=token,
            prompt_message="Confirm",
        ),
        created_at=now,
        expires_at=expires_at,
        plan_hash=plan_hash,
    )


def test_approve_valid_modify_plan() -> None:
    store = PlanStore()
    plan = make_test_plan("p-1", risk_level=RiskLevel.MODIFY)
    store.store_plan(plan)

    approved = store.approve_plan("p-1", provided_hash=plan.plan_hash)
    assert approved.plan.plan_id == "p-1"
    assert approved.approved_at > 0


def test_replay_attack_rejected() -> None:
    store = PlanStore()
    plan = make_test_plan("p-replay", risk_level=RiskLevel.MODIFY)
    store.store_plan(plan)

    store.approve_plan("p-replay", provided_hash=plan.plan_hash)

    # Invariant 7: Plan cannot be reused or replayed
    with pytest.raises(PermissionError, match="consumed and cannot be re-approved"):
        store.approve_plan("p-replay", provided_hash=plan.plan_hash)


def test_expired_plan_cannot_be_approved() -> None:
    store = PlanStore()
    plan = make_test_plan("p-expired", risk_level=RiskLevel.MODIFY, expires_in=-10.0)
    store.store_plan(plan)

    with pytest.raises(TimeoutError, match="has expired"):
        store.approve_plan("p-expired", provided_hash=plan.plan_hash)


def test_hash_tampering_rejected() -> None:
    store = PlanStore()
    plan = make_test_plan("p-hash", risk_level=RiskLevel.MODIFY)
    store.store_plan(plan)

    with pytest.raises(ValueError, match="Plan hash mismatch"):
        store.approve_plan("p-hash", provided_hash="tampered-fake-hash-value")


def test_destructive_token_mismatch_rejected() -> None:
    store = PlanStore()
    plan = make_test_plan("p-destruct", risk_level=RiskLevel.DESTRUCTIVE, token="DELETE 3")
    store.store_plan(plan)

    with pytest.raises(PermissionError, match="Confirmation token mismatch"):
        store.approve_plan("p-destruct", provided_hash=plan.plan_hash, confirmation_input="WRONG")

    # Correct token succeeds
    approved = store.approve_plan(
        "p-destruct", provided_hash=plan.plan_hash, confirmation_input="DELETE 3"
    )
    assert approved.confirmation_input == "DELETE 3"
