"""Tests for core domain models and plan hashing."""

import time

import pytest

from shellsense.models import (
    ApprovedPlan,
    ConfirmationHint,
    ConfirmationKind,
    Plan,
    RiskLevel,
    TargetFile,
    compute_plan_hash,
)


def create_sample_plan(
    operation: str = "MOVE",
    risk_level: RiskLevel = RiskLevel.MODIFY,
    expires_in: float = 120.0,
) -> Plan:
    now = time.time()
    expires_at = now + expires_in
    target = TargetFile(
        path="/tmp/test.txt",
        exists=True,
        is_dir=False,
        size_bytes=1024,
        inode=12345,
        device=6789,
        mtime=now,
    )
    plan_hash = compute_plan_hash(
        operation=operation,
        target_files=(target,),
        target_processes=(),
        parameters={"dest": "/tmp/dest.txt"},
        risk_level=risk_level,
        summary="Move test file",
        consequences="File will be moved",
        created_at=now,
        expires_at=expires_at,
    )
    return Plan(
        plan_id="plan-1234",
        operation=operation,
        target_files=(target,),
        target_processes=(),
        parameters={"dest": "/tmp/dest.txt"},
        risk_level=risk_level,
        summary="Move test file",
        consequences="File will be moved",
        confirmation_hint=ConfirmationHint(
            kind=ConfirmationKind.BUTTON,
            token=None,
            prompt_message="Click approve to move file",
        ),
        created_at=now,
        expires_at=expires_at,
        plan_hash=plan_hash,
    )


def test_plan_hash_verification() -> None:
    plan = create_sample_plan()
    assert plan.verify_hash() is True


def test_tampered_plan_hash_fails_verification() -> None:
    plan = create_sample_plan()
    # Create plan with forged hash
    tampered_plan = Plan(
        plan_id=plan.plan_id,
        operation=plan.operation,
        target_files=plan.target_files,
        target_processes=plan.target_processes,
        parameters={"dest": "/malicious/dest.txt"},  # Tampered parameter
        risk_level=plan.risk_level,
        summary=plan.summary,
        consequences=plan.consequences,
        confirmation_hint=plan.confirmation_hint,
        created_at=plan.created_at,
        expires_at=plan.expires_at,
        plan_hash=plan.plan_hash,
    )
    assert tampered_plan.verify_hash() is False


def test_approved_plan_direct_construction_blocked() -> None:
    plan = create_sample_plan()
    with pytest.raises(PermissionError, match="ApprovedPlan cannot be constructed directly"):
        ApprovedPlan(
            plan=plan,
            approved_at=time.time(),
            confirmation_input=None,
        )
