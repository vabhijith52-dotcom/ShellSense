"""Chat routing endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from shellsense.api.schemas import (
    ChatMessageRequest,
    ChatResponse,
    ClarificationMessage,
    ExplanationInfo,
    PlanPreviewMessage,
    RefusalMessage,
    ResultMessage,
)
from shellsense.executor.executor import DEFAULT_EXECUTOR
from shellsense.models import RiskLevel
from shellsense.nlp.context import DEFAULT_SESSION_CONTEXT
from shellsense.nlp.rule_based import DEFAULT_PARSER
from shellsense.nlp.schemas import Clarification, Refusal
from shellsense.planner import DEFAULT_PLANNER
from shellsense.safety.approval import DEFAULT_PLAN_STORE
from shellsense.storage.audit import DEFAULT_AUDIT_LOGGER, AuditDecision

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/messages", response_model=ChatResponse)
async def send_chat_message(req: ChatMessageRequest) -> ChatResponse:
    """Process natural-language prompt through the security pipeline."""
    # 1. NLP Parse
    parsed = DEFAULT_PARSER.parse(req.text, session_id="chat")
    if isinstance(parsed, Refusal):
        DEFAULT_AUDIT_LOGGER.log(
            session_id="chat",
            original_text=req.text,
            intent="REFUSED",
            plan_hash=None,
            risk=RiskLevel.BLOCKED,
            decision=AuditDecision.REFUSED,
            errors=[parsed.reason],
        )
        return RefusalMessage(reason=parsed.reason)
    if isinstance(parsed, Clarification):
        return ClarificationMessage(question=parsed.question, options=parsed.options)

    # Contextual explanation info for transparency
    cmd_info = DEFAULT_SESSION_CONTEXT.get_last_parsed_command("chat")
    understood_as = cmd_info.get("understood_as") if cmd_info else None
    explanation = (
        ExplanationInfo(
            operation=cmd_info["operation"],
            params=cmd_info.get("params", {}),
            confidence=float(cmd_info.get("confidence", 1.0)),
            defaults_applied=list(cmd_info.get("defaults_applied", [])),
            resolved_scope=str(cmd_info.get("resolved_scope", "")),
        )
        if cmd_info
        else None
    )

    # 2. Plan creation
    try:
        plan = DEFAULT_PLANNER.create_plan(parsed)
    except PermissionError as pe:
        DEFAULT_AUDIT_LOGGER.log(
            session_id="chat",
            original_text=req.text,
            intent=parsed.operation,
            plan_hash=None,
            risk=RiskLevel.BLOCKED,
            decision=AuditDecision.DENIED,
            errors=[str(pe)],
        )
        return RefusalMessage(reason=str(pe))
    except Exception as exc:
        return RefusalMessage(reason=f"Unable to plan operation: {exc}")

    # Store plan in server-side PlanStore
    DEFAULT_PLAN_STORE.store_plan(plan)

    # 3. If SAFE: auto-approve and execute immediately (Invariant 6 & Table in Section 7)
    if plan.risk_level == RiskLevel.SAFE:
        approved = DEFAULT_PLAN_STORE.approve_plan(plan.plan_id, plan.plan_hash)
        result = DEFAULT_EXECUTOR.execute(approved)
        summary_msg = result.outcomes[0].message if result.outcomes else "Completed"
        return ResultMessage(
            status=result.status.value,
            summary=summary_msg,
            errors=result.errors,
            understood_as=understood_as,
            explanation=explanation,
        )

    # 4. If MODIFY or DESTRUCTIVE: Return PlanPreview for user approval
    return PlanPreviewMessage(
        plan_id=plan.plan_id,
        plan_hash=plan.plan_hash,
        risk=plan.risk_level.value,
        summary=plan.summary,
        targets=[f.path for f in plan.target_files] or [str(p.pid) for p in plan.target_processes],
        consequences=plan.consequences,
        confirmation_kind=plan.confirmation_hint.kind.value,
        confirmation_token=plan.confirmation_hint.token,
        confirmation_hint=plan.confirmation_hint.prompt_message,
        understood_as=understood_as,
        explanation=explanation,
    )
