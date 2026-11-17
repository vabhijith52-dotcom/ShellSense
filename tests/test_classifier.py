"""Tests for fail-closed risk classification engine."""

import pytest

from shellsense.models import RiskLevel
from shellsense.safety.classifier import classify_risk


@pytest.mark.parametrize(
    ("op", "expected"),
    [
        ("SHOW_MEMORY", RiskLevel.SAFE),
        ("SHOW_CPU", RiskLevel.SAFE),
        ("SHOW_DISK", RiskLevel.SAFE),
        ("LIST_FILES", RiskLevel.SAFE),
        ("FIND_FILES", RiskLevel.SAFE),
        ("CREATE_FOLDER", RiskLevel.MODIFY),
        ("CREATE_ARCHIVE", RiskLevel.MODIFY),
        ("MOVE", RiskLevel.MODIFY),
        ("COPY", RiskLevel.MODIFY),
        ("RENAME", RiskLevel.MODIFY),
        ("TRASH_FILES", RiskLevel.DESTRUCTIVE),
        ("CLEAN_TEMP", RiskLevel.DESTRUCTIVE),
        ("TERMINATE_PROCESS", RiskLevel.DESTRUCTIVE),
        ("SUDO", RiskLevel.BLOCKED),
        ("ELEVATE", RiskLevel.BLOCKED),
        ("RUN_COMMAND", RiskLevel.BLOCKED),
        ("PACKAGE_INSTALL", RiskLevel.BLOCKED),
        ("RANDOM_UNKNOWN_OP", RiskLevel.BLOCKED),
        ("", RiskLevel.BLOCKED),
        (None, RiskLevel.BLOCKED),
    ],
)
def test_classification_matrix(op: str | None, expected: RiskLevel) -> None:
    assert classify_risk(op) == expected


def test_overwrite_elevates_to_destructive() -> None:
    # Normally MODIFY
    assert classify_risk("MOVE", is_overwrite=False) == RiskLevel.MODIFY
    # Overwrite elevates to DESTRUCTIVE per Section 7
    assert classify_risk("MOVE", is_overwrite=True) == RiskLevel.DESTRUCTIVE


def test_bulk_operations_elevate_to_destructive() -> None:
    assert classify_risk("MOVE", target_count=1) == RiskLevel.MODIFY
    assert classify_risk("MOVE", target_count=5) == RiskLevel.DESTRUCTIVE


def test_fail_closed_on_exceptions() -> None:
    # Passing unexpected types must fail closed to BLOCKED
    assert classify_risk(12345) == RiskLevel.BLOCKED  # type: ignore[arg-type]
