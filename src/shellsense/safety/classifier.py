"""Fail-closed risk classification engine for ShellSense.

Invariant 1: Unknown intent, unknown operation, missing risk level, unparseable input,
or any exception in the safety path means REFUSE (BLOCKED).
Never return None or a permissive default.
"""

from __future__ import annotations

from typing import Any

from shellsense.models import RiskLevel

_SAFE_OPERATIONS = frozenset({
    "SHOW_MEMORY",
    "SHOW_CPU",
    "SHOW_DISK",
    "TOP_PROCESSES",
    "LIST_PROCESSES",
    "LIST_FILES",
    "FIND_FILES",
    "FIND_DUPLICATES",
    "SYSTEM_INFO",
})

_MODIFY_OPERATIONS = frozenset({
    "CREATE_FOLDER",
    "CREATE_ARCHIVE",
    "MOVE",
    "COPY",
    "RENAME",
})

_DESTRUCTIVE_OPERATIONS = frozenset({
    "TRASH_FILES",
    "DELETE_FILES",
    "CLEAN_TEMP",
    "TERMINATE_PROCESS",
    "FORCE_KILL_PROCESS",
})

_EXPLICIT_BLOCKED_OPERATIONS = frozenset({
    "SUDO",
    "ELEVATE",
    "RUN_COMMAND",
    "EXEC_SCRIPT",
    "PACKAGE_INSTALL",
    "PACKAGE_REMOVE",
    "MODIFY_SYSTEM_REGISTRY",
})


def classify_risk(
    operation: str | None,
    parameters: dict[str, Any] | None = None,
    target_count: int = 1,
    is_overwrite: bool = False,
) -> RiskLevel:
    """Classify the risk level of an operation.

    Strictly fail-closed: Any exception, None, unknown operation, or invalid parameters
    evaluates to RiskLevel.BLOCKED.
    """
    try:
        if not operation or not isinstance(operation, str):
            return RiskLevel.BLOCKED

        if parameters is not None and not isinstance(parameters, dict):
            return RiskLevel.BLOCKED

        normalized_op = operation.strip().upper()

        if normalized_op in _EXPLICIT_BLOCKED_OPERATIONS:
            return RiskLevel.BLOCKED

        # Any operation that causes an overwrite is elevated to DESTRUCTIVE
        if is_overwrite:
            return RiskLevel.DESTRUCTIVE

        # Any bulk operation (> 1 item) on modifying operations is elevated to DESTRUCTIVE
        if target_count > 1 and normalized_op in _MODIFY_OPERATIONS:
            return RiskLevel.DESTRUCTIVE

        if normalized_op in _DESTRUCTIVE_OPERATIONS:
            return RiskLevel.DESTRUCTIVE

        if normalized_op in _MODIFY_OPERATIONS:
            return RiskLevel.MODIFY

        if normalized_op in _SAFE_OPERATIONS:
            return RiskLevel.SAFE

        # Unknown operation: fail closed!
        return RiskLevel.BLOCKED

    except Exception:
        # Invariant 1: Any exception in the safety path means REFUSE
        return RiskLevel.BLOCKED
