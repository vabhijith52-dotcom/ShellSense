"""Safety engine exports for ShellSense."""

from shellsense.safety.approval import DEFAULT_PLAN_STORE, PlanStore
from shellsense.safety.classifier import classify_risk
from shellsense.safety.consent import ConsentRecord, PermissionGate
from shellsense.safety.path_guard import PathGuard

__all__ = [
    "classify_risk",
    "PathGuard",
    "ConsentRecord",
    "PermissionGate",
    "PlanStore",
    "DEFAULT_PLAN_STORE",
]
