"""Plan generation engine for ShellSense.

Resolves concrete filesystem and process targets, builds canonical hash,
and freezes an immutable Plan.
"""

from __future__ import annotations

from shellsense.models import Intent, Plan
from shellsense.operations import GLOBAL_REGISTRY
from shellsense.safety.consent import PermissionGate


class Planner:
    """Read-only planner that converts an Intent into a frozen Plan."""

    def __init__(self, permission_gate: PermissionGate | None = None) -> None:
        self.permission_gate = permission_gate or PermissionGate()

    def create_plan(self, intent: Intent) -> Plan:
        """Convert a validated Intent into a Plan with resolved targets and hash.

        Raises PermissionError if capability not granted, or KeyError if operation unknown.
        """
        op = GLOBAL_REGISTRY.get_by_intent(intent.operation)
        if op is None:
            raise KeyError(f"Unknown operation for intent '{intent.operation}'.")

        # Invariant 11: Capability must be granted
        if not self.permission_gate.has_capability(op.required_capability):
            raise PermissionError(
                f"Capability '{op.required_capability.value}' is required for operation '{op.name}', "
                f"but ShellSense has not been granted this permission."
            )

        granted_roots = self.permission_gate.get_granted_roots()

        # Build plan via registered operation (read-only)
        plan = op.plan(
            params=intent.params,
            original_text=intent.original_text,
            allowed_roots=granted_roots,
        )

        return plan


DEFAULT_PLANNER = Planner()
