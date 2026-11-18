"""Operation registry and base Operation protocol.

Scalability rule (Section 5): Every capability is one self-contained Operation registered here.
It declares: name and intents, params_schema, required capability, risk_level,
plan(params), preview(plan), execute(approved_plan), and optional undo(record).
Registration strictly fails if any required component is missing.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

from shellsense.models import (
    ApprovedPlan,
    Capability,
    Plan,
    Result,
    RiskLevel,
)


class BaseOperation(ABC):
    """Abstract base class for all ShellSense operations."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique operation name (e.g. SHOW_MEMORY, MOVE, TRASH_FILES)."""
        ...

    @property
    @abstractmethod
    def intents(self) -> tuple[str, ...]:
        """Tuple of intent names mapped to this operation."""
        ...

    @property
    @abstractmethod
    def params_schema(self) -> type[BaseModel]:
        """Pydantic model schema for validating parameters."""
        ...

    @property
    @abstractmethod
    def required_capability(self) -> Capability:
        """The capability grant required to plan or execute this operation."""
        ...

    @property
    def catalog_examples(self) -> tuple[str, ...]:
        """Catalog examples of natural language requests for this operation."""
        return ()

    @abstractmethod
    def compute_risk(self, params: dict[str, Any]) -> RiskLevel:
        """Compute the fail-closed risk level based on parameters."""
        ...

    @abstractmethod
    def plan(
        self,
        params: dict[str, Any],
        original_text: str = "",
        allowed_roots: list[Any] | None = None,
    ) -> Plan:
        """Read-only target resolution and plan construction.

        Resolves concrete targets (inode, device, mtime, PID, create_time),
        computes the canonical SHA-256 plan hash, and sets expiry.
        """
        ...

    @abstractmethod
    def preview(self, plan: Plan) -> dict[str, Any]:
        """Generate structured preview metadata for the UI."""
        ...

    @abstractmethod
    def execute(self, approved_plan: ApprovedPlan) -> Result:
        """Execute the operation using exclusively the ApprovedPlan.

        This method is invoked ONLY by executor.py after all safety re-verifications.
        """
        ...

    def undo(self, undo_record: dict[str, Any]) -> Result | None:
        """Optional undo implementation for reversible operations."""
        return None


class OperationRegistry:
    """Registry managing available operations."""

    def __init__(self) -> None:
        self._operations: dict[str, BaseOperation] = {}
        self._intent_map: dict[str, BaseOperation] = {}

    def register(self, operation: BaseOperation) -> None:
        """Register an operation. Fails if incomplete or duplicate."""
        if not operation.name or not isinstance(operation.name, str):
            raise ValueError("Operation must have a valid non-empty string name.")
        if not operation.intents:
            raise ValueError(f"Operation '{operation.name}' must declare at least one intent.")
        if not issubclass(operation.params_schema, BaseModel):
            raise ValueError(f"Operation '{operation.name}' params_schema must be a Pydantic model.")
        if not isinstance(operation.required_capability, Capability):
            raise ValueError(f"Operation '{operation.name}' required_capability must be a Capability enum.")
        if not hasattr(operation, "catalog_examples") or not isinstance(operation.catalog_examples, (tuple, list)):
            raise ValueError(f"Operation '{operation.name}' must provide catalog_examples.")

        op_name = operation.name.upper()
        if op_name in self._operations:
            raise KeyError(f"Operation '{op_name}' is already registered.")

        self._operations[op_name] = operation
        for intent in operation.intents:
            self._intent_map[intent.upper()] = operation

    def get_by_name(self, name: str) -> BaseOperation | None:
        return self._operations.get(name.upper())

    def get_by_intent(self, intent: str) -> BaseOperation | None:
        return self._intent_map.get(intent.upper())

    def list_operations(self) -> list[str]:
        return sorted(self._operations.keys())

    def list_intents(self) -> list[str]:
        return sorted(self._intent_map.keys())


# Singleton operation registry
GLOBAL_REGISTRY = OperationRegistry()
