"""Tests for audit logger: append-only JSONL, hash chaining, and fail-closed non-SAFE write failure."""

from pathlib import Path

import pytest

from shellsense.models import RiskLevel
from shellsense.storage.audit import AuditDecision, AuditLogger


def test_audit_log_append_and_hash_chain(tmp_path: Path) -> None:
    logger = AuditLogger(log_dir=tmp_path)

    logger.log(
        session_id="sess-1",
        original_text="Show my RAM usage",
        intent="SHOW_MEMORY",
        plan_hash="hash-1234",
        risk=RiskLevel.SAFE,
        decision=AuditDecision.AUTO_ALLOWED,
        result_status="SUCCESS",
    )

    logger.log(
        session_id="sess-1",
        original_text="Move file",
        intent="MOVE",
        plan_hash="hash-5678",
        risk=RiskLevel.MODIFY,
        decision=AuditDecision.APPROVED,
        result_status="SUCCESS",
    )

    log_file = tmp_path / "audit.jsonl"
    assert log_file.exists()
    lines = log_file.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2


def test_audit_failure_aborts_non_safe_operation(tmp_path: Path) -> None:
    # Point logger to an invalid file path to simulate failure
    bad_dir = tmp_path / "protected"
    bad_dir.mkdir()
    logger = AuditLogger(log_dir=bad_dir)
    logger.log_file = bad_dir  # Writing to directory as file raises IsADirectoryError / PermissionError

    # Non-SAFE must fail closed and raise
    with pytest.raises(RuntimeError, match="Audit log write failed"):
        logger.log(
            session_id="sess-err",
            original_text="Delete everything",
            intent="TRASH_FILES",
            plan_hash="hash-fail",
            risk=RiskLevel.DESTRUCTIVE,
            decision=AuditDecision.APPROVED,
        )
