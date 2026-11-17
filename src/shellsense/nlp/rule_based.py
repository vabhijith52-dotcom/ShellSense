"""Rule-based, schema-first NLP parser for ShellSense.

Uses regex, keywords, and rapidfuzz string matching to parse user requests into
validated Intents, Clarifications, or Refusals.
"""

from __future__ import annotations

import re

from rapidfuzz import fuzz

from shellsense.models import Intent
from shellsense.nlp.schemas import Clarification, Refusal
from shellsense.safety.sanitize import sanitize_text

# Blocked patterns (Invariant 2 & 3: No sudo, shell, or elevation)
_BLOCKED_PATTERNS = [
    re.compile(r"\b(sudo|su|runas|elevate|admin|administrator|root)\b", re.IGNORECASE),
    re.compile(r"\b(bash|sh|cmd\.exe|powershell|wsl|exec|eval)\b", re.IGNORECASE),
    re.compile(r"\b(apt|dnf|pacman|choco|winget|brew|yum)\s+(install|remove)", re.IGNORECASE),
    re.compile(r"\brm\s+-rf\s+/", re.IGNORECASE),
]


class RuleBasedParser:
    """Deterministic, rule-based intent parser."""

    def parse(self, text: str) -> Intent | Clarification | Refusal:
        raw_text = sanitize_text(text).strip()
        if not raw_text:
            return Clarification(
                question="What would you like ShellSense to help you with?",
                options=[
                    "Show my system usage",
                    "Find large files",
                    "Delete temporary files",
                    "List running processes",
                ],
                original_text=raw_text,
            )

        # 1. Check for blocked keywords / privilege escalation
        for pattern in _BLOCKED_PATTERNS:
            if pattern.search(raw_text):
                return Refusal(
                    reason="Privileged, shell-injected, or package management commands are forbidden.",
                    original_text=raw_text,
                )

        lower_text = raw_text.lower()

        # 2. System info & metrics
        if self._matches(lower_text, ["show my system usage", "system usage", "system info", "specs"]):
            return Intent(
                operation="SYSTEM_INFO",
                params={"metric": "all"},
                confidence=0.95,
                original_text=raw_text,
            )

        if self._matches(lower_text, ["show my ram usage", "ram usage", "memory usage", "how much ram", "memory"]):
            return Intent(
                operation="SHOW_MEMORY",
                params={"metric": "memory"},
                confidence=0.95,
                original_text=raw_text,
            )

        if self._matches(lower_text, ["show cpu usage", "cpu usage", "cpu percent", "processor usage", "cpu"]):
            return Intent(
                operation="SHOW_CPU",
                params={"metric": "cpu"},
                confidence=0.95,
                original_text=raw_text,
            )

        if self._matches(lower_text, ["show disk usage", "disk usage", "disk space", "storage", "free space"]):
            return Intent(
                operation="SHOW_DISK",
                params={"metric": "disk"},
                confidence=0.95,
                original_text=raw_text,
            )

        # 3. Process management
        if self._matches(lower_text, ["list running processes", "list processes", "running processes", "ps"]):
            return Intent(
                operation="LIST_PROCESSES",
                params={"limit": 50},
                confidence=0.95,
                original_text=raw_text,
            )

        if self._matches(lower_text, ["top processes", "highest cpu processes", "top cpu"]):
            return Intent(
                operation="TOP_PROCESSES",
                params={"sort_by": "cpu", "limit": 10},
                confidence=0.9,
                original_text=raw_text,
            )

        # Terminate process pattern: "kill process 1234", "terminate PID 4567"
        term_match = re.search(r"\b(kill|terminate|stop|end)\s+(?:process\s+|pid\s+)?(\d+)\b", lower_text)
        if term_match:
            pid = int(term_match.group(2))
            return Intent(
                operation="TERMINATE_PROCESS",
                params={"pids": [pid]},
                confidence=0.95,
                original_text=raw_text,
            )

        term_name_match = re.search(r"\b(kill|terminate|stop|end)\s+process\s+([a-zA-Z0-9_\-\.]+)\b", lower_text)
        if term_name_match:
            proc_name = term_name_match.group(2)
            return Intent(
                operation="TERMINATE_PROCESS",
                params={"process_name": proc_name},
                confidence=0.9,
                original_text=raw_text,
            )

        # 4. Large files & duplicates
        if self._matches(lower_text, ["find large files", "scan large files", "large files"]):
            # Extract size if present (e.g. "> 500MB")
            min_size = self._parse_size(lower_text) or (100 * 1024 * 1024)
            return Intent(
                operation="FIND_FILES",
                params={"min_size_bytes": min_size},
                confidence=0.9,
                original_text=raw_text,
            )

        if self._matches(lower_text, ["find duplicate files", "find duplicates", "duplicate files", "duplicates"]):
            return Intent(
                operation="FIND_DUPLICATES",
                params={},
                confidence=0.95,
                original_text=raw_text,
            )

        if self._matches(lower_text, ["delete temporary files", "clean temp", "clean temporary files", "temp cleanup"]):
            return Intent(
                operation="CLEAN_TEMP",
                params={},
                confidence=0.95,
                original_text=raw_text,
            )

        # 5. File Operations: Create folder, archive, move, copy, rename, delete
        create_folder_match = re.search(r"\b(create|make|new)\s+folder\s+(.+)", lower_text)
        if create_folder_match:
            folder_name = create_folder_match.group(2).strip()
            return Intent(
                operation="CREATE_FOLDER",
                params={"name": folder_name},
                confidence=0.9,
                original_text=raw_text,
            )

        archive_match = re.search(r"\b(create|make)\s+archive\s+(?:of\s+)?(.+)", lower_text)
        if archive_match:
            target = archive_match.group(2).strip()
            return Intent(
                operation="CREATE_ARCHIVE",
                params={"target": target},
                confidence=0.9,
                original_text=raw_text,
            )

        delete_match = re.search(r"\b(delete|trash|remove)\s+(?:file\s+)?(.+)", lower_text)
        if delete_match:
            target_file = delete_match.group(2).strip()
            return Intent(
                operation="TRASH_FILES",
                params={"targets": [target_file]},
                confidence=0.9,
                original_text=raw_text,
            )

        # Fallback Clarification when confidence is low
        return Clarification(
            question="I didn't quite understand that request. Would you like to try one of these?",
            options=[
                "Show my system usage",
                "Find large files",
                "Delete temporary files",
                "List running processes",
            ],
            original_text=raw_text,
        )

    def _matches(self, text: str, phrases: list[str], threshold: float = 85.0) -> bool:
        """Check exact substring or rapidfuzz match."""
        for phrase in phrases:
            if phrase in text:
                return True
            if fuzz.partial_ratio(text, phrase) >= threshold:
                return True
        return False

    def _parse_size(self, text: str) -> int | None:
        """Parse size strings like '500MB', '1GB', '100 MB'."""
        match = re.search(r"(\d+(?:\.\d+)?)\s*(gb|mb|kb|g|m|k)", text, re.IGNORECASE)
        if not match:
            return None
        val = float(match.group(1))
        unit = match.group(2).upper()
        if unit.startswith("G"):
            return int(val * 1024 * 1024 * 1024)
        if unit.startswith("M"):
            return int(val * 1024 * 1024)
        if unit.startswith("K"):
            return int(val * 1024)
        return None


DEFAULT_PARSER = RuleBasedParser()
