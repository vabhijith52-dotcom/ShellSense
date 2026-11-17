"""Protocol definition for natural-language intent parsers."""

from __future__ import annotations

from typing import Protocol

from shellsense.models import Intent
from shellsense.nlp.schemas import Clarification, Refusal


class IntentParser(Protocol):
    """Protocol for intent parsers (rule-based or future LLM)."""

    def parse(self, text: str) -> Intent | Clarification | Refusal:
        """Parse raw untrusted user text into a validated Intent, Clarification, or Refusal."""
        ...
