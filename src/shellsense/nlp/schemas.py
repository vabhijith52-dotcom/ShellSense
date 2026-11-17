"""NLP schemas and data contracts.

Invariant 5: The NLP layer can only produce an Intent or a Clarification.
It never produces commands, never names targets in an approval, and never calls the executor.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Clarification(BaseModel):
    """Returned when a user request is ambiguous or missing required parameters."""
    model_config = ConfigDict(frozen=True)

    question: str
    options: list[str] = Field(default_factory=list)
    original_text: str
    partial_intent: str | None = None


class Refusal(BaseModel):
    """Returned when a request violates security invariants or requests forbidden operations."""
    model_config = ConfigDict(frozen=True)

    reason: str
    original_text: str
