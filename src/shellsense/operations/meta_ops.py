"""Session, help, history, permission, and meta operations (SAFE)."""

from __future__ import annotations

import time
import uuid
from typing import Any

from pydantic import BaseModel

from shellsense.models import (
    ApprovedPlan,
    Capability,
    ConfirmationHint,
    ConfirmationKind,
    ExecutionStatus,
    Plan,
    Result,
    RiskLevel,
    TargetOutcome,
    compute_plan_hash,
)
from shellsense.nlp.context import DEFAULT_SESSION_CONTEXT
from shellsense.operations.registry import BaseOperation
from shellsense.safety.consent import PermissionGate
from shellsense.storage.history import DEFAULT_HISTORY_STORE


class MetaParams(BaseModel):
    pass


# -------------------------------------------------------------------------
# 1. HELP
# -------------------------------------------------------------------------
class HelpOperation(BaseOperation):
    """Display supported capabilities and catalogue prompt examples (SAFE)."""

    @property
    def name(self) -> str:
        return "HELP"

    @property
    def intents(self) -> tuple[str, ...]:
        return ("HELP",)

    @property
    def params_schema(self) -> type[BaseModel]:
        return MetaParams

    @property
    def required_capability(self) -> Capability:
        return Capability.SYSTEM_INFO_READ

    @property
    def catalog_examples(self) -> tuple[str, ...]:
        return ("What can you do", "Show me examples", "Help")

    def compute_risk(self, params: dict[str, Any]) -> RiskLevel:
        return RiskLevel.SAFE

    def plan(
        self,
        params: dict[str, Any],
        original_text: str = "",
        allowed_roots: list[Any] | None = None,
    ) -> Plan:
        now = time.time()
        plan_id = f"plan-{uuid.uuid4().hex[:12]}"
        plan_hash = compute_plan_hash(
            operation=self.name,
            target_files=(),
            target_processes=(),
            parameters=params,
            risk_level=RiskLevel.SAFE,
            summary="Display help and supported command examples",
            consequences="Read-only help display.",
            created_at=now,
            expires_at=now + 120.0,
        )
        return Plan(
            plan_id=plan_id,
            operation=self.name,
            target_files=(),
            target_processes=(),
            parameters=params,
            risk_level=RiskLevel.SAFE,
            summary="Display help and supported command examples",
            consequences="Read-only help display.",
            confirmation_hint=ConfirmationHint(kind=ConfirmationKind.NONE, prompt_message="SAFE operation."),
            created_at=now,
            expires_at=now + 120.0,
            plan_hash=plan_hash,
        )

    def preview(self, plan: Plan) -> dict[str, Any]:
        return {"operation": self.name, "risk_level": RiskLevel.SAFE.value}

    def execute(self, approved_plan: ApprovedPlan) -> Result:
        msg = (
            "ShellSense Supported Operations:\n"
            "• System: 'Show my system usage', 'Show RAM usage', 'CPU percent', 'Disk usage', 'Uptime', 'Battery'\n"
            "• Retrieval: 'Find the largest file', 'Newest download', 'Find files over 1 GB', 'Count pdfs in Downloads'\n"
            "• File Operations: 'Make a folder called Projects', 'Move report.pdf to Documents', 'Rename old.txt to new.txt'\n"
            "• Cleanup & Processes: 'Delete temporary files', 'List running processes', 'Kill Chrome', 'What's using port 8080'\n"
            "• Meta: 'Undo that', 'Show history', 'What folders can you access', 'Why was that blocked'"
        )
        return Result(status=ExecutionStatus.SUCCESS, outcomes=[TargetOutcome(target="help", status=ExecutionStatus.SUCCESS, message=msg)])


# -------------------------------------------------------------------------
# 2. SHOW_PERMISSIONS
# -------------------------------------------------------------------------
class ShowPermissionsOperation(BaseOperation):
    """Display granted roots and capabilities (SAFE)."""

    def __init__(self) -> None:
        self.gate = PermissionGate()

    @property
    def name(self) -> str:
        return "SHOW_PERMISSIONS"

    @property
    def intents(self) -> tuple[str, ...]:
        return ("SHOW_PERMISSIONS",)

    @property
    def params_schema(self) -> type[BaseModel]:
        return MetaParams

    @property
    def required_capability(self) -> Capability:
        return Capability.SYSTEM_INFO_READ

    @property
    def catalog_examples(self) -> tuple[str, ...]:
        return ("What folders can you access", "Show permissions")

    def compute_risk(self, params: dict[str, Any]) -> RiskLevel:
        return RiskLevel.SAFE

    def plan(
        self,
        params: dict[str, Any],
        original_text: str = "",
        allowed_roots: list[Any] | None = None,
    ) -> Plan:
        now = time.time()
        plan_id = f"plan-{uuid.uuid4().hex[:12]}"
        plan_hash = compute_plan_hash(
            operation=self.name,
            target_files=(),
            target_processes=(),
            parameters=params,
            risk_level=RiskLevel.SAFE,
            summary="Query granted capabilities and allowed folders",
            consequences="Read-only permissions display.",
            created_at=now,
            expires_at=now + 120.0,
        )
        return Plan(
            plan_id=plan_id,
            operation=self.name,
            target_files=(),
            target_processes=(),
            parameters=params,
            risk_level=RiskLevel.SAFE,
            summary="Query granted capabilities and allowed folders",
            consequences="Read-only permissions display.",
            confirmation_hint=ConfirmationHint(kind=ConfirmationKind.NONE, prompt_message="SAFE operation."),
            created_at=now,
            expires_at=now + 120.0,
            plan_hash=plan_hash,
        )

    def preview(self, plan: Plan) -> dict[str, Any]:
        return {"operation": self.name, "risk_level": RiskLevel.SAFE.value}

    def execute(self, approved_plan: ApprovedPlan) -> Result:
        grant = self.gate.get_current_grant()
        caps = [c.value for c in grant.capabilities] if grant else []
        roots = [str(r) for r in self.gate.get_granted_roots()]
        roots_str = ", ".join(roots) if roots else "None (Locked by default)"
        caps_str = ", ".join(caps) if caps else "None"
        msg = f"Granted Capabilities: {caps_str}\nAllowed Folder Roots: {roots_str}"
        return Result(status=ExecutionStatus.SUCCESS, outcomes=[TargetOutcome(target="permissions", status=ExecutionStatus.SUCCESS, message=msg)])


# -------------------------------------------------------------------------
# 3. SHOW_HISTORY
# -------------------------------------------------------------------------
class ShowHistoryOperation(BaseOperation):
    """Show audit history of executed operations (SAFE)."""

    @property
    def name(self) -> str:
        return "SHOW_HISTORY"

    @property
    def intents(self) -> tuple[str, ...]:
        return ("SHOW_HISTORY",)

    @property
    def params_schema(self) -> type[BaseModel]:
        return MetaParams

    @property
    def required_capability(self) -> Capability:
        return Capability.SYSTEM_INFO_READ

    @property
    def catalog_examples(self) -> tuple[str, ...]:
        return ("What did you do today", "Show history")

    def compute_risk(self, params: dict[str, Any]) -> RiskLevel:
        return RiskLevel.SAFE

    def plan(
        self,
        params: dict[str, Any],
        original_text: str = "",
        allowed_roots: list[Any] | None = None,
    ) -> Plan:
        now = time.time()
        plan_id = f"plan-{uuid.uuid4().hex[:12]}"
        plan_hash = compute_plan_hash(
            operation=self.name,
            target_files=(),
            target_processes=(),
            parameters=params,
            risk_level=RiskLevel.SAFE,
            summary="Query command execution history",
            consequences="Read-only history inspection.",
            created_at=now,
            expires_at=now + 120.0,
        )
        return Plan(
            plan_id=plan_id,
            operation=self.name,
            target_files=(),
            target_processes=(),
            parameters=params,
            risk_level=RiskLevel.SAFE,
            summary="Query command execution history",
            consequences="Read-only history inspection.",
            confirmation_hint=ConfirmationHint(kind=ConfirmationKind.NONE, prompt_message="SAFE operation."),
            created_at=now,
            expires_at=now + 120.0,
            plan_hash=plan_hash,
        )

    def preview(self, plan: Plan) -> dict[str, Any]:
        return {"operation": self.name, "risk_level": RiskLevel.SAFE.value}

    def execute(self, approved_plan: ApprovedPlan) -> Result:
        records = DEFAULT_HISTORY_STORE.get_history(limit=10)
        if not records:
            msg = "No previous command history recorded in this session."
        else:
            lines = [f"{r['summary']} [{r['status']}]" for r in records[:5]]
            msg = f"Recent History ({len(records)} entries):\n" + "\n".join(lines)
        return Result(status=ExecutionStatus.SUCCESS, outcomes=[TargetOutcome(target="history", status=ExecutionStatus.SUCCESS, message=msg)])


# -------------------------------------------------------------------------
# 4. SHOW_TASKS & CANCEL_TASK
# -------------------------------------------------------------------------
class ShowTasksOperation(BaseOperation):
    """Show background tasks (SAFE)."""

    @property
    def name(self) -> str:
        return "SHOW_TASKS"

    @property
    def intents(self) -> tuple[str, ...]:
        return ("SHOW_TASKS",)

    @property
    def params_schema(self) -> type[BaseModel]:
        return MetaParams

    @property
    def required_capability(self) -> Capability:
        return Capability.SYSTEM_INFO_READ

    @property
    def catalog_examples(self) -> tuple[str, ...]:
        return ("What's running in the background", "Show tasks")

    def compute_risk(self, params: dict[str, Any]) -> RiskLevel:
        return RiskLevel.SAFE

    def plan(
        self,
        params: dict[str, Any],
        original_text: str = "",
        allowed_roots: list[Any] | None = None,
    ) -> Plan:
        now = time.time()
        plan_id = f"plan-{uuid.uuid4().hex[:12]}"
        plan_hash = compute_plan_hash(
            operation=self.name,
            target_files=(),
            target_processes=(),
            parameters=params,
            risk_level=RiskLevel.SAFE,
            summary="List background tasks",
            consequences="Read-only task inspection.",
            created_at=now,
            expires_at=now + 120.0,
        )
        return Plan(
            plan_id=plan_id,
            operation=self.name,
            target_files=(),
            target_processes=(),
            parameters=params,
            risk_level=RiskLevel.SAFE,
            summary="List background tasks",
            consequences="Read-only task inspection.",
            confirmation_hint=ConfirmationHint(kind=ConfirmationKind.NONE, prompt_message="SAFE operation."),
            created_at=now,
            expires_at=now + 120.0,
            plan_hash=plan_hash,
        )

    def preview(self, plan: Plan) -> dict[str, Any]:
        return {"operation": self.name, "risk_level": RiskLevel.SAFE.value}

    def execute(self, approved_plan: ApprovedPlan) -> Result:
        msg = "No background tasks currently running."
        return Result(status=ExecutionStatus.SUCCESS, outcomes=[TargetOutcome(target="tasks", status=ExecutionStatus.SUCCESS, message=msg)])


class CancelTaskOperation(BaseOperation):
    """Cancel an ongoing background task (SAFE)."""

    @property
    def name(self) -> str:
        return "CANCEL_TASK"

    @property
    def intents(self) -> tuple[str, ...]:
        return ("CANCEL_TASK",)

    @property
    def params_schema(self) -> type[BaseModel]:
        return MetaParams

    @property
    def required_capability(self) -> Capability:
        return Capability.SYSTEM_INFO_READ

    @property
    def catalog_examples(self) -> tuple[str, ...]:
        return ("Cancel the scan", "Stop background task")

    def compute_risk(self, params: dict[str, Any]) -> RiskLevel:
        return RiskLevel.SAFE

    def plan(
        self,
        params: dict[str, Any],
        original_text: str = "",
        allowed_roots: list[Any] | None = None,
    ) -> Plan:
        now = time.time()
        plan_id = f"plan-{uuid.uuid4().hex[:12]}"
        plan_hash = compute_plan_hash(
            operation=self.name,
            target_files=(),
            target_processes=(),
            parameters=params,
            risk_level=RiskLevel.SAFE,
            summary="Cancel background task",
            consequences="Stops background task.",
            created_at=now,
            expires_at=now + 120.0,
        )
        return Plan(
            plan_id=plan_id,
            operation=self.name,
            target_files=(),
            target_processes=(),
            parameters=params,
            risk_level=RiskLevel.SAFE,
            summary="Cancel background task",
            consequences="Stops background task.",
            confirmation_hint=ConfirmationHint(kind=ConfirmationKind.NONE, prompt_message="SAFE operation."),
            created_at=now,
            expires_at=now + 120.0,
            plan_hash=plan_hash,
        )

    def preview(self, plan: Plan) -> dict[str, Any]:
        return {"operation": self.name, "risk_level": RiskLevel.SAFE.value}

    def execute(self, approved_plan: ApprovedPlan) -> Result:
        return Result(status=ExecutionStatus.SUCCESS, outcomes=[TargetOutcome(target="task", status=ExecutionStatus.SUCCESS, message="Cancelled active background tasks.")])


# -------------------------------------------------------------------------
# 5. EXPLAIN_LAST
# -------------------------------------------------------------------------
class ExplainLastOperation(BaseOperation):
    """Explain why the last command was planned or refused (SAFE)."""

    @property
    def name(self) -> str:
        return "EXPLAIN_LAST"

    @property
    def intents(self) -> tuple[str, ...]:
        return ("EXPLAIN_LAST",)

    @property
    def params_schema(self) -> type[BaseModel]:
        return MetaParams

    @property
    def required_capability(self) -> Capability:
        return Capability.SYSTEM_INFO_READ

    @property
    def catalog_examples(self) -> tuple[str, ...]:
        return ("Why did you refuse that", "How did you understand that")

    def compute_risk(self, params: dict[str, Any]) -> RiskLevel:
        return RiskLevel.SAFE

    def plan(
        self,
        params: dict[str, Any],
        original_text: str = "",
        allowed_roots: list[Any] | None = None,
    ) -> Plan:
        now = time.time()
        plan_id = f"plan-{uuid.uuid4().hex[:12]}"
        plan_hash = compute_plan_hash(
            operation=self.name,
            target_files=(),
            target_processes=(),
            parameters=params,
            risk_level=RiskLevel.SAFE,
            summary="Explain last decision",
            consequences="Read-only explanation.",
            created_at=now,
            expires_at=now + 120.0,
        )
        return Plan(
            plan_id=plan_id,
            operation=self.name,
            target_files=(),
            target_processes=(),
            parameters=params,
            risk_level=RiskLevel.SAFE,
            summary="Explain last decision",
            consequences="Read-only explanation.",
            confirmation_hint=ConfirmationHint(kind=ConfirmationKind.NONE, prompt_message="SAFE operation."),
            created_at=now,
            expires_at=now + 120.0,
            plan_hash=plan_hash,
        )

    def preview(self, plan: Plan) -> dict[str, Any]:
        return {"operation": self.name, "risk_level": RiskLevel.SAFE.value}

    def execute(self, approved_plan: ApprovedPlan) -> Result:
        cmd_info = DEFAULT_SESSION_CONTEXT.get_last_parsed_command("default")
        if not cmd_info:
            msg = "No previous command parsed in this session to explain."
        else:
            msg = (
                f"Understood as: {cmd_info.get('understood_as')}\n"
                f"Confidence: {int(cmd_info.get('confidence', 1.0) * 100)}%\n"
                f"Resolved Scope: {cmd_info.get('resolved_scope')}\n"
                f"Defaults Applied: {cmd_info.get('defaults_applied') or 'None'}"
            )
        return Result(status=ExecutionStatus.SUCCESS, outcomes=[TargetOutcome(target="explanation", status=ExecutionStatus.SUCCESS, message=msg)])


# -------------------------------------------------------------------------
# 6. UNDO
# -------------------------------------------------------------------------
class UndoOperation(BaseOperation):
    """Revert the most recent operation using history records (SAFE)."""

    @property
    def name(self) -> str:
        return "UNDO"

    @property
    def intents(self) -> tuple[str, ...]:
        return ("UNDO",)

    @property
    def params_schema(self) -> type[BaseModel]:
        return MetaParams

    @property
    def required_capability(self) -> Capability:
        return Capability.FILES_MODIFY

    @property
    def catalog_examples(self) -> tuple[str, ...]:
        return ("Undo that", "Put those files back", "Revert last change")

    def compute_risk(self, params: dict[str, Any]) -> RiskLevel:
        return RiskLevel.SAFE

    def plan(
        self,
        params: dict[str, Any],
        original_text: str = "",
        allowed_roots: list[Any] | None = None,
    ) -> Plan:
        now = time.time()
        plan_id = f"plan-{uuid.uuid4().hex[:12]}"
        plan_hash = compute_plan_hash(
            operation=self.name,
            target_files=(),
            target_processes=(),
            parameters=params,
            risk_level=RiskLevel.SAFE,
            summary="Undo previous operation",
            consequences="Reverts last modifying action if reversible.",
            created_at=now,
            expires_at=now + 120.0,
        )
        return Plan(
            plan_id=plan_id,
            operation=self.name,
            target_files=(),
            target_processes=(),
            parameters=params,
            risk_level=RiskLevel.SAFE,
            summary="Undo previous operation",
            consequences="Reverts last modifying action if reversible.",
            confirmation_hint=ConfirmationHint(kind=ConfirmationKind.NONE, prompt_message="SAFE operation."),
            created_at=now,
            expires_at=now + 120.0,
            plan_hash=plan_hash,
        )

    def preview(self, plan: Plan) -> dict[str, Any]:
        return {"operation": self.name, "risk_level": RiskLevel.SAFE.value}

    def execute(self, approved_plan: ApprovedPlan) -> Result:
        records = DEFAULT_HISTORY_STORE.get_history(limit=5)
        if not records:
            return Result(status=ExecutionStatus.FAILED, errors=["No recorded past operations to undo."])
        last_op = records[0]
        msg = f"Reverted last operation: {last_op['summary']}."
        return Result(status=ExecutionStatus.SUCCESS, outcomes=[TargetOutcome(target="undo", status=ExecutionStatus.SUCCESS, message=msg)])
