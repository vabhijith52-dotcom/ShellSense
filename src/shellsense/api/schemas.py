"""API request and response schemas (Section 11 contract)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatMessageRequest(BaseModel):
    text: str = Field(..., max_length=2000)


class TextMessage(BaseModel):
    kind: Literal["text"] = "text"
    text: str


class InfoTable(BaseModel):
    kind: Literal["info_table"] = "info_table"
    title: str
    headers: list[str]
    rows: list[list[str]]


class ClarificationMessage(BaseModel):
    kind: Literal["clarification"] = "clarification"
    question: str
    options: list[str]


class PlanPreviewMessage(BaseModel):
    kind: Literal["plan_preview"] = "plan_preview"
    plan_id: str
    plan_hash: str
    risk: str
    summary: str
    targets: list[str]
    consequences: str
    confirmation_kind: str
    confirmation_token: str | None = None
    confirmation_hint: str


class RefusalMessage(BaseModel):
    kind: Literal["refusal"] = "refusal"
    reason: str


class ResultMessage(BaseModel):
    kind: Literal["result"] = "result"
    status: str
    summary: str
    errors: list[str] = Field(default_factory=list)


ChatResponse = TextMessage | InfoTable | ClarificationMessage | PlanPreviewMessage | RefusalMessage | ResultMessage


class ApprovePlanRequest(BaseModel):
    """Approval request payload.

    Invariant 7: Client can never send targets or parameters in an approval.
    """
    model_config = ConfigDict(extra="forbid")

    plan_hash: str
    confirmation_input: str | None = None


class FilePlanRequest(BaseModel):
    action: str
    sources: list[str] = Field(default_factory=list)
    destination: str | None = None


class ProcessPlanRequest(BaseModel):
    action: str
    pids: list[int] = Field(default_factory=list)


class GrantPermissionRequest(BaseModel):
    capabilities: list[str]
    folder_roots: list[str]
    confirmation_phrase: str
    nonce: str


class SettingsUpdateRequest(BaseModel):
    confidence_threshold: float | None = None
    bulk_item_limit: int | None = None
    plan_expiry_seconds: int | None = None
