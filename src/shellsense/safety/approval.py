"""Plan storage, hash verification, single-use binding, and approval engine.

Enforces Invariant 6 (only ApprovedPlan executable) and Invariant 7 (single-use exact hash binding).
"""

from __future__ import annotations

import hmac
import threading
import time

from shellsense.models import (
    _APPROVED_PLAN_SENTINEL,
    ApprovedPlan,
    Plan,
    RiskLevel,
)


class PlanStore:
    """Thread-safe in-memory store for pending plans and single-use approval tracking."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._plans: dict[str, Plan] = {}
        self._consumed_plans: set[str] = set()

    def store_plan(self, plan: Plan) -> str:
        """Store a newly generated plan by its unique plan_id."""
        with self._lock:
            # Validate integrity of hash before storing
            if not plan.verify_hash():
                raise ValueError("Cannot store plan: Hash mismatch with canonical fields.")
            self._plans[plan.plan_id] = plan
            return plan.plan_id

    def get_plan(self, plan_id: str) -> Plan | None:
        """Retrieve a stored plan if it exists and has not expired."""
        with self._lock:
            plan = self._plans.get(plan_id)
            if plan is None:
                return None
            if time.time() > plan.expires_at:
                return None
            return plan

    def approve_plan(
        self,
        plan_id: str,
        provided_hash: str,
        confirmation_input: str | None = None,
    ) -> ApprovedPlan:
        """Validate approval request and return an immutable ApprovedPlan.

        Invariants:
        1. Plan must exist and not be expired.
        2. Plan cannot have been previously approved or consumed (No replay).
        3. Provided hash must match plan hash using constant-time comparison.
        4. DESTRUCTIVE operations must provide exact matching confirmation token.
        5. Once approved, the plan is marked consumed.
        """
        with self._lock:
            if plan_id in self._consumed_plans:
                raise PermissionError("Plan has already been consumed and cannot be re-approved.")

            plan = self._plans.get(plan_id)
            if plan is None:
                raise KeyError(f"Plan '{plan_id}' not found.")

            # Expiry check
            current_time = time.time()
            if current_time > plan.expires_at:
                raise TimeoutError(f"Plan '{plan_id}' has expired.")

            # Constant-time plan hash comparison to prevent timing leaks
            if not hmac.compare_digest(plan.plan_hash, provided_hash):
                raise ValueError("Plan hash mismatch. The plan may have been altered or corrupted.")

            # Verify typed confirmation token for destructive operations
            if plan.risk_level == RiskLevel.DESTRUCTIVE:
                expected_token = plan.confirmation_hint.token
                token_mismatch = (
                    expected_token is not None
                    and (
                        not confirmation_input
                        or confirmation_input.strip() != expected_token.strip()
                    )
                )
                if token_mismatch:
                    raise PermissionError(
                        f"Confirmation token mismatch. Expected '{expected_token}', "
                        f"got '{confirmation_input}'."
                    )

            # Mark plan as consumed to prevent replay attacks
            self._consumed_plans.add(plan_id)
            del self._plans[plan_id]

            # Construct ApprovedPlan using private sentinel
            return ApprovedPlan(
                plan=plan,
                approved_at=current_time,
                confirmation_input=confirmation_input,
                _sentinel=_APPROVED_PLAN_SENTINEL,
            )

    def deny_plan(self, plan_id: str) -> bool:
        """Explicitly deny/cancel a pending plan."""
        with self._lock:
            if plan_id in self._plans:
                del self._plans[plan_id]
                self._consumed_plans.add(plan_id)
                return True
            return False

    def clear(self) -> None:
        """Clear all active and consumed plans (used in testing)."""
        with self._lock:
            self._plans.clear()
            self._consumed_plans.clear()


# Global plan store instance
DEFAULT_PLAN_STORE = PlanStore()
