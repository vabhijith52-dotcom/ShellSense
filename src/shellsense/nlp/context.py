"""Server-side session context store for ShellSense NLP follow-ups and explanations.

Handles result sets from previous retrieval operations so users can say:
'delete them', 'move those to Backup', 'zip the first three', 'delete the largest one'.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ResultSetItem:
    """An item in a stored retrieval result set."""
    path: str
    is_dir: bool = False
    size_bytes: int | None = None
    mtime: float | None = None
    name: str = ""


@dataclass
class StoredResultSet:
    """A collection of retrieval items stored server-side for context follow-up."""
    result_set_id: str
    items: list[ResultSetItem]
    operation: str
    created_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 600.0)  # 10 min window


class SessionContextStore:
    """Thread-safe in-memory store for session result sets and command explanations."""

    def __init__(self) -> None:
        self._result_sets: dict[str, StoredResultSet] = {}
        self._last_result_set_by_session: dict[str, str] = {}
        self._last_parsed_by_session: dict[str, dict[str, Any]] = {}

    def store_result_set(
        self,
        session_id: str,
        operation: str,
        items: list[dict[str, Any]],
    ) -> str:
        """Store a retrieval result set server-side."""
        rs_id = f"rs-{uuid.uuid4().hex[:8]}"
        parsed_items: list[ResultSetItem] = []
        for it in items:
            p = it.get("path") or it.get("name") or ""
            parsed_items.append(
                ResultSetItem(
                    path=p,
                    is_dir=bool(it.get("is_dir", False)),
                    size_bytes=it.get("size_bytes"),
                    mtime=it.get("mtime"),
                    name=it.get("name") or p,
                )
            )

        rs = StoredResultSet(
            result_set_id=rs_id,
            items=parsed_items,
            operation=operation,
        )
        self._result_sets[rs_id] = rs
        self._last_result_set_by_session[session_id] = rs_id
        return rs_id

    def get_last_result_set(self, session_id: str) -> StoredResultSet | None:
        """Fetch the most recent result set for the given session."""
        rs_id = self._last_result_set_by_session.get(session_id)
        if not rs_id:
            return None
        rs = self._result_sets.get(rs_id)
        if not rs or time.time() > rs.expires_at:
            return None
        return rs

    def resolve_context_reference(
        self,
        session_id: str,
        ref: str,
    ) -> list[str]:
        """Resolve a reference like 'them', 'first 3', 'largest one' to concrete file paths."""
        rs = self.get_last_result_set(session_id)
        if not rs or not rs.items:
            return []

        lower_ref = ref.lower().strip()
        if lower_ref in {"them", "those", "these files", "these items", "all"}:
            return [it.path for it in rs.items]

        if "first" in lower_ref:
            import re
            m = re.search(r"first\s+(\d+)", lower_ref)
            count = int(m.group(1)) if m else 1
            return [it.path for it in rs.items[:count]]

        if "largest" in lower_ref:
            # Sort by size if available
            sorted_items = sorted(
                rs.items,
                key=lambda x: x.size_bytes or 0,
                reverse=True,
            )
            return [sorted_items[0].path] if sorted_items else []

        if "videos" in lower_ref or "images" in lower_ref or "photos" in lower_ref:
            # Filter by extension
            from shellsense.nlp.entities import FILE_TYPE_GROUPS
            target_exts = FILE_TYPE_GROUPS.get("videos", set()) if "video" in lower_ref else FILE_TYPE_GROUPS.get("images", set())
            matched = [it.path for it in rs.items if any(it.path.lower().endswith(e) for e in target_exts)]
            return matched

        return [it.path for it in rs.items]

    def record_parsed_command(
        self,
        session_id: str,
        command_info: dict[str, Any],
    ) -> None:
        """Record the explanation metadata of the last parsed command."""
        self._last_parsed_by_session[session_id] = command_info

    def get_last_parsed_command(self, session_id: str) -> dict[str, Any] | None:
        """Fetch explanation info of the last parsed command for EXPLAIN_LAST."""
        return self._last_parsed_by_session.get(session_id)


# Global singleton context store
DEFAULT_SESSION_CONTEXT = SessionContextStore()
