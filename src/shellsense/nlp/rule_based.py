"""Rule-based, schema-first NLP parser for ShellSense.

Uses entity extraction, normalized text, weighted synonym families,
rapidfuzz typo tolerance, and fail-closed safety checks.
"""

from __future__ import annotations

import re
from typing import Any

from rapidfuzz import fuzz

from shellsense.models import Intent, RiskLevel
from shellsense.nlp.context import DEFAULT_SESSION_CONTEXT
from shellsense.nlp.entities import (
    ExtractedEntities,
    check_negation,
    extract_entities,
)
from shellsense.nlp.schemas import Clarification, Refusal

# Standard catalogue fallback suggestions
_CATALOGUE_SUGGESTIONS = [
    "Show my system usage",
    "Find the largest file",
    "List running processes",
    "Delete temporary files",
    "What's using port 8080",
]


def clean_input(text: str) -> str:
    """Prepare text for matching by normalizing contractions and stripping leading conversational filler."""
    cleaned = text.strip()
    lowered = cleaned.lower()
    lowered = re.sub(r"\bwhat's\b", "what is", lowered)
    lowered = re.sub(r"\bwhats\b", "what is", lowered)
    lowered = re.sub(r"\bcan't\b", "cannot", lowered)
    lowered = re.sub(r"\bdon't\b", "do not", lowered)
    lowered = re.sub(r"\bdont\b", "do not", lowered)
    lowered = re.sub(r"\bdidn't\b", "did not", lowered)
    lowered = re.sub(r"\bwon't\b", "will not", lowered)
    lowered = re.sub(r"\bit's\b", "it is", lowered)
    lowered = re.sub(r"^(?:please|could you please|can you please|kindly|hey shellsense,?\s*)\s*", "", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


class RuleBasedParser:
    """Comprehensive, deterministic rule-based natural language parser."""

    def parse(self, text: str, session_id: str = "default") -> Intent | Clarification | Refusal:
        raw_text = text.strip() if text else ""
        if not raw_text:
            return Clarification(
                question="What would you like ShellSense to help you with?",
                options=_CATALOGUE_SUGGESTIONS[:4],
                original_text=raw_text,
            )

        # 1. Negation Check: "don't delete X" never produces a plan
        if check_negation(raw_text):
            return Refusal(
                reason="Negation detected: ShellSense will not perform an operation you asked not to do.",
                original_text=raw_text,
            )

        cleaned = clean_input(raw_text)
        entities = extract_entities(cleaned, original_text=raw_text)

        # 2. Blocked keywords / Privilege escalation / Forbidden commands (fail-closed)
        is_process_inspection = (
            bool(re.search(r"\b(process|running|active)\s+bash\b", raw_text, re.IGNORECASE))
            or bool(re.search(r"\b(look\s+for\s+process|find\s+process|is\s+process)\b", raw_text, re.IGNORECASE))
        )
        if not is_process_inspection and re.search(r"\b(bash|sh|cmd\.exe|powershell|wsl)\b", raw_text, re.IGNORECASE):
            return Refusal(
                reason="Shell execution (bash, cmd.exe, powershell) is forbidden by security policy.",
                original_text=raw_text,
            )

        if re.search(r"\b(sudo|runas|elevate|administrator)\b", raw_text, re.IGNORECASE) or re.search(r"\b(run\s+as\s+root|su\s+root)\b", raw_text, re.IGNORECASE):
            return Refusal(
                reason="Privilege escalation (sudo, root, administrator) is forbidden.",
                original_text=raw_text,
            )

        if re.search(r"\b(apt|apt-get|dnf|pacman|choco|winget|brew|yum)\s+(install|remove)", raw_text, re.IGNORECASE):
            return Refusal(
                reason="Package management operations are forbidden.",
                original_text=raw_text,
            )

        if re.search(r"\brm\s+-rf\b|\bdel\s+/s\b|\bformat\s+[a-zA-Z]:|\b(empty\s+(?:the\s+)?recycle\s+bin|empty\s+trash)\b|\bdelete\s+everything\b", raw_text, re.IGNORECASE):
            return Refusal(
                reason="Permanent deletion, disk formatting, or whole-system removal is forbidden.",
                original_text=raw_text,
            )

        if re.search(r"^(?:sudo\s+)?(?:shutdown|reboot)\b", raw_text, re.IGNORECASE) and not re.search(r"\b(since|how\s+long|uptime)\b", raw_text, re.IGNORECASE):
            return Refusal(
                reason="System shutdown and reboot commands are forbidden.",
                original_text=raw_text,
            )

        # 3. Pattern matching & Intent scoring
        intent_match, confidence, params, defaults = self._match_intent(cleaned, raw_text, entities, session_id)

        # 4. Handle Context Reference ("delete them", "move those", "zip the first 3")
        if entities.context_ref:
            resolved_targets = DEFAULT_SESSION_CONTEXT.resolve_context_reference(session_id, entities.context_ref)
            if resolved_targets:
                params["targets"] = resolved_targets
                if not intent_match:
                    if "delete" in cleaned or "trash" in cleaned:
                        intent_match = "TRASH_FILES"
                        confidence = 0.95
                    elif "zip" in cleaned or "archive" in cleaned:
                        intent_match = "CREATE_ARCHIVE"
                        confidence = 0.90
                    elif "move" in cleaned:
                        intent_match = "MOVE"
                        confidence = 0.90

        if not intent_match:
            return Clarification(
                question="I didn't quite understand that request. Would you like to try one of these?",
                options=self._get_closest_suggestions(cleaned),
                original_text=raw_text,
            )

        # 5. Confidence policy check (SAFE >= 0.70, MODIFY/DESTRUCTIVE >= 0.85)
        risk = self._get_intent_risk(intent_match)
        min_threshold = 0.70 if risk == RiskLevel.SAFE else 0.85

        if confidence < min_threshold:
            if confidence >= 0.50:
                return Clarification(
                    question=f"Did you mean to {self._format_intent_name(intent_match)}?",
                    options=[f"{self._format_intent_name(intent_match)}", "Show my system usage", "Help"],
                    original_text=raw_text,
                    partial_intent=intent_match,
                )
            return Clarification(
                question="I didn't quite understand that request. Would you like to try one of these?",
                options=self._get_closest_suggestions(cleaned),
                original_text=raw_text,
            )

        # 6. Record parsed explanation in session context
        DEFAULT_SESSION_CONTEXT.record_parsed_command(
            session_id=session_id,
            command_info={
                "operation": intent_match,
                "params": params,
                "confidence": confidence,
                "defaults_applied": defaults,
                "resolved_scope": params.get("path") or "all granted roots",
                "understood_as": f"{self._format_intent_name(intent_match)} ({params})",
                "original_text": raw_text,
            },
        )

        return Intent(
            operation=intent_match,
            params=params,
            confidence=confidence,
            original_text=raw_text,
        )

    def _match_intent(
        self,
        text: str,
        raw_text: str,
        entities: ExtractedEntities,
        session_id: str,
    ) -> tuple[str | None, float, dict[str, Any], list[str]]:
        # --- SESSION & META (Phase E) ---
        if re.search(r"\b(undo\s+that|undo\s+last|undo\s+rename|undo\s+file|undo\s+my|undo\b|put\s+those\s+files\s+back|revert\s+last|revert\s+previous|restore\s+last|take\s+back\s+last|cancel\s+last|rollback|restore\s+what\s+was)\b", text):
            return "UNDO", 0.98, {}, []

        if re.search(r"\b(why\s+did\s+you|explain\s+last|why\s+was\s+that|why\s+was\s+my|explain\s+your\s+decision|how\s+did\s+you\s+understand|breakdown\s+of\s+last|why\s+didn'?t\s+you|explain\s+why|why\s+you\s+did\s+that|why\s+did\s+not\s+you\s+execute|explain\s+(?:the\s+)?last\s+plan)\b", text):
            return "EXPLAIN_LAST", 0.95, {}, []

        if re.search(r"\b(what\s+did\s+you\s+do|show\s+deletions|show\s+history|view\s+past\s+commands|operations\s+were\s+executed|audit\s+history|history\s+of\s+commands|show\s+command\s+log|view\s+execution\s+history|show\s+recent\s+activity|show\s+past\s+operations|display\s+history|history\b|what\s+was\s+done\s+yesterday|list\s+past\s+actions|what\s+did\s+shellsense\s+do)\b", text):
            return "SHOW_HISTORY", 0.95, {}, []

        if re.search(r"\b(cancel\s+(?:the\s+)?scan|stop\s+background\s+task|cancel\s+running\s+task|abort\s+current\s+task|stop\s+(?:the\s+)?background\s+job|cancel\s+task|abort\s+scan|kill\s+background\s+task|stop\s+task|cancel\s+active\s+scan|terminate\s+background|end\s+current\s+task|cancel\s+job|halt\s+background|abort\s+task)\b", text):
            return "CANCEL_TASK", 0.95, {}, []

        if re.search(r"\b(what\s+can\s+you\s+do|show\s+(?:me\s+)?examples|how\s+do\s+i\s+use|commands\s+do\s+you\s+support|show\s+supported\s+operations|list\s+available\s+commands|give\s+me\s+example\s+prompts|what\s+operations\s+are\s+available|command\s+catalog|guide\s+me|help\s+me|show\s+help|explain\s+what\s+you\s+can\s+do|what\s+are\s+some\s+things\s+i\s+can\s+ask|help\b)\b", text):
            return "HELP", 0.98, {}, []

        if re.search(r"\b(folders\s+can\s+you\s+access|show\s+permissions|granted\s+roots|which\s+directories\s+are\s+permitted|permitted\s+directories|check\s+granted\s+capabilities|show\s+allowed\s+folders|what\s+capabilities\s+do\s+you\s+have|granted\s+permissions|permission\s+gate|folders\s+are\s+allowed|view\s+permissions|system\s+access\s+rights|which\s+folders\s+can\s+shellsense|capability\s+grants|what\s+am\s+i\s+allowing|what\s+folders\s+can\s+shellsense\s+read)\b", text):
            return "SHOW_PERMISSIONS", 0.95, {}, []

        # --- DELETIONS & CLEANUPS (Phase D) ---
        if re.search(r"\b(delete\s+temporary|clean\s+temp|clean\s+temporary|temp\s+cleanup|remove\s+temporary|clear\s+temp|temporary\s+cache|empty\s+temp\s+directory|clean\s+system\s+temporary|purge\s+temporary|delete\s+all\s+temp|trash\s+temporary|cleaning\s+temp|clean\s+user\s+temp|get\s+rid\s+of\s+temp\s+files)\b", text):
            return "CLEAN_TEMP", 0.95, {"max_age_days": 1}, ["default max_age 24 hours"]

        if re.search(r"\b(remove|delete|trash|clean\s+up|clean\s+out|purge|clear|get\s+rid\s+of)\s+(?:any\s+|all\s+)?(?:empty\s+(?:folders|directories)|(?:0|zero)-item\s+directories|folders\s+that\s+are\s+empty)\b", text):
            return "DELETE_EMPTY_FOLDERS", 0.95, {"path": entities.path or ""}, []

        if re.search(r"\b(delete\s+(?:the\s+)?folder|trash\s+(?:the\s+)?folder|trash\s+directory|remove\s+folder|delete\s+directory|move\s+folder\s+[a-zA-Z0-9_\-\.]+\s+to\s+trash|delete\s+the\s+[a-zA-Z0-9_\-\.]+\s+directory|trash\s+this\s+folder|get\s+rid\s+of\s+folder|trash\s+folder\s+called|remove\s+directory)\b", text):
            m = re.search(r"(?:folder|directory)\s+([a-zA-Z0-9_\-\.\/\\]+)", raw_text, re.IGNORECASE)
            tgt = m.group(1).strip() if m else (entities.path or "")
            return "TRASH_FOLDER", 0.92, {"path": tgt}, []

        if re.search(r"\b(delete\s+file|trash\s+[a-zA-Z0-9_\-\.]+\.[a-zA-Z0-9]+|remove\s+file|delet\s+[a-zA-Z0-9_\-\.]+|delete\s+all\s+files|remove\s+everything\s+older|delete\s+(?:the\s+)?\d+\s+largest|get\s+rid\s+of\s+my\s+old\s+installers|move\s+[a-zA-Z0-9_\-\.]+\s+to\s+trash|remove\s+document|get\s+rid\s+of\s+[a-zA-Z0-9_\-\.]+|trash\s+these\s+files|delete\s+them|delete\s+[a-zA-Z0-9_\-\.\/\\]+\.[a-zA-Z0-9]+)\b", text) or re.search(r"delete\s+[a-zA-Z]:\\", raw_text, re.IGNORECASE):
            targets = []
            if entities.name_pattern:
                targets.append(entities.name_pattern)
            elif entities.path:
                targets.append(entities.path)
            else:
                del_m = re.search(r"(?:delete|trash|remove|delet|get\s+rid\s+of)\s+(?:file\s+)?([a-zA-Z0-9_\-\.\/\\]+)", raw_text, re.IGNORECASE)
                if del_m and del_m.group(1).strip() not in {"them", "those", "temporary", "temp", "everything", "all"}:
                    targets.append(del_m.group(1).strip())
            return "TRASH_FILES", 0.92, {
                "targets": targets,
                "min_size_bytes": entities.min_size_bytes,
                "time_cutoff": entities.time_cutoff_seconds,
                "count": entities.count,
            }, []

        # --- TEXT & FILE MODIFICATIONS (Phase C) ---
        if re.search(r"\b(add\s+['\"][^'\"]+['\"]\s+to\s+the\s+end|append\s+['\"][^'\"]+['\"]\s+to|add\s+line\s+to|append\s+text|add\s+text\s+to\s+the\s+end|add\s+entry\s+to|append\s+string\s+to|write\s+to\s+the\s+end\s+of|add\s+to\s+file|add\s+['\"][^'\"]+['\"]\s+to\s+[a-zA-Z0-9_\-\.]+|append\s+note\s+to|add\s+text\s+['\"][^'\"]+['\"]\s+to|append\s+line\s+['\"][^'\"]+['\"]\s+to)\b", text):
            target_match = re.search(r"(?:to|into)\s+([a-zA-Z0-9_\-\.\/\\]+)", raw_text, re.IGNORECASE)
            fname = entities.name_pattern or (target_match.group(1).strip() if target_match else "")
            text_match = re.search(r"(?:add|append)\s+['\"]?([^'\"\n]+)['\"]?\s+(?:to|into)", raw_text, re.IGNORECASE)
            content = text_match.group(1) if text_match else ""
            return "APPEND_TEXT", 0.92, {"path": fname, "content": content}, []

        if re.search(r"\b(batch\s+rename|bulk\s+rename|number\s+these\s+files|prefix\s+all|add\s+prefix|rename\s+all\s+\.[a-zA-Z0-9]+\s+(?:files\s+)?to|number\s+all\s+files|add\s+suffix|change\s+prefix|replace\s+space\s+with\s+underscore|replace\s+[a-zA-Z0-9_\-]+\s+with\s+[a-zA-Z0-9_\-]+\s+in|add\s+the\s+date\s+to\s+the\s+start)\b", text):
            return "BATCH_RENAME", 0.90, {"path": entities.path or "", "pattern": text}, []

        if re.search(r"\b(rename\s+[a-zA-Z0-9_\-\.\/\\]+\s+to|call\s+it\s+[a-zA-Z0-9_\-\.]+|rename\s+file|change\s+name\s+of|call\s+document\.pdf|give\s+[a-zA-Z0-9_\-\.]+\s+the\s+name|change\s+filename\s+of|rename\s+this\s+file\s+to|rename\s+photo\.jpg\s+to|rename\s+folder\s+oldprojects\s+to|rename\s+script\.py\s+to|rename\s+report_v1\.pdf\s+to|rename\s+image\.png\s+to)\b", text) or re.search(r"rename\s+[a-zA-Z]:\\", raw_text, re.IGNORECASE):
            m = re.search(r"rename\s+(?:file\s+|folder\s+)?([a-zA-Z0-9_\-\.\/\\]+)\s+to\s+([a-zA-Z0-9_\-\.]+)", raw_text, re.IGNORECASE)
            if m:
                return "RENAME", 0.92, {"source": m.group(1), "new_name": m.group(2)}, []
            m2 = re.search(r"call\s+(?:it\s+)?([a-zA-Z0-9_\-\.]+)", raw_text, re.IGNORECASE)
            if m2:
                return "RENAME", 0.88, {"source": "", "new_name": m2.group(1)}, []
            m3 = re.search(r"change\s+(?:name|filename)\s+of\s+([a-zA-Z0-9_\-\.\/\\]+)\s+to\s+([a-zA-Z0-9_\-\.]+)", raw_text, re.IGNORECASE)
            if m3:
                return "RENAME", 0.92, {"source": m3.group(1), "new_name": m3.group(2)}, []
            return "RENAME", 0.90, {}, []

        if re.search(r"\b(move\s+[a-zA-Z0-9_\-\.\/\\]+\s+to|move\s+those\s+to|move\s+file|relocate\s+(?:folder\s+)?[a-zA-Z0-9_\-\.\/\\]+\s+to|put\s+[a-zA-Z0-9_\-\.\/\\]+\s+into|transfer\s+[a-zA-Z0-9_\-\.\/\\]+\s+to|put\s+[a-zA-Z0-9_\-\.\/\\]+\s+in|move\s+[a-zA-Z0-9_\-\.\/\\]+\s+from\s+[a-zA-Z0-9_\-\.\/\\]+\s+to\s+[a-zA-Z0-9_\-\.\/\\]+)\b", text) or re.search(r"move\s+[a-zA-Z]:\\", raw_text, re.IGNORECASE):
            m = re.search(r"(?:move|relocate|put|transfer)\s+(?:folder\s+)?([a-zA-Z0-9_\-\.\/\\]+)", raw_text, re.IGNORECASE)
            src = entities.name_pattern or (m.group(1).strip() if m else "")
            return "MOVE", 0.90, {"source": src, "destination": entities.destination_path or ""}, []

        if re.search(r"\b(copy\s+(?:the\s+)?[a-zA-Z0-9_\-\.\/\\]+(?:\s+folder)?\s+to|duplicate\s+file|make\s+a\s+copy\s+of|replicate\s+folder|copy\s+file\s+[a-zA-Z0-9_\-\.]+|copy\s+this\s+folder\s+to|copy\s+[a-zA-Z0-9_\-\.]+\s+to\s+[a-zA-Z0-9_\-\.]+|make\s+a\s+copy\s+of\s+invoice\.pdf|duplicate\s+[a-zA-Z0-9_\-\.]+\s+into)\b", text) or re.search(r"copy\s+[a-zA-Z]:\\", raw_text, re.IGNORECASE):
            m = re.search(r"(?:copy|duplicate|replicate)\s+(?:the\s+|file\s+|folder\s+)?([a-zA-Z0-9_\-\.\/\\]+)", raw_text, re.IGNORECASE)
            src = entities.name_pattern or (m.group(1).strip() if m else "")
            return "COPY", 0.90, {"source": src, "destination": entities.destination_path or ""}, []

        if re.search(r"\b(create\s+a\s+folder|make\s+a\s+folder|make\s+a\s+new\s+folder|create\s+directory|new\s+folder|make\s+folder|add\s+folder|create\s+a\s+directory|new\s+directory|create\s+folder)\b", text):
            m = re.search(r"(?:called|named|folder|directory)\s+([a-zA-Z0-9_\-\.\s]+)", raw_text, re.IGNORECASE)
            name = entities.name_pattern or (m.group(1).strip() if m else "NewFolder")
            name = re.sub(r"\s+in\s+.*$", "", name, flags=re.IGNORECASE).strip()
            return "CREATE_FOLDER", 0.92, {"name": name, "parent": entities.path or ""}, []

        if re.search(r"\b(create\s+notes\.txt|make\s+todo\.md|create\s+file|make\s+a\s+new\s+file|create\s+empty\s+file|make\s+file|create\s+a\s+text\s+file|write\s+a\s+new\s+file|create\s+document|make\s+new\s+file|create\s+a\s+file\s+named)\b", text):
            m = re.search(r"(?:called|named|file)\s+([a-zA-Z0-9_\-\.]+)", raw_text, re.IGNORECASE)
            fname = entities.name_pattern or (m.group(1).strip() if m else "notes.txt")
            content_match = re.search(r"(?:text|containing|content|with text)\s+['\"]?([^'\"\n]+)['\"]?", raw_text, re.IGNORECASE)
            content = content_match.group(1) if content_match else ""
            return "CREATE_FILE", 0.92, {"name": fname, "content": content, "parent": entities.path or ""}, []

        if re.search(r"\b(organize\s+(?:my\s+)?[a-zA-Z0-9_\-\.\/\\]+\s+by\s+file\s+type|sort\s+files\s+in\s+[a-zA-Z0-9_\-\.\/\\]+\s+into\s+folders|organize\s+this\s+folder\s+by\s+type|clean\s+up\s+downloads\s+by\s+categorizing|sort\s+downloads\s+into|group\s+files\s+in|arrange\s+files\s+by\s+extension|categorize\s+files|sort\s+folder\s+by\s+file\s+type|organize\s+my\s+files\s+by\s+type|organize\s+pictures\s+and\s+documents|group\s+documents\s+by\s+file\s+extension|organize\s+files\s+in\s+[a-zA-Z0-9_\-\.]+\s+by\s+type|organize\s+files\s+into\s+category)\b", text) or re.search(r"organize\s+[a-zA-Z]:\\", raw_text, re.IGNORECASE):
            return "ORGANIZE_BY_TYPE", 0.92, {"path": entities.path or ""}, []

        # --- FILE DETAILS & READ (before archives) ---
        if re.search(r"\b(details\s+of|file\s+info\s+for|when\s+was\s+[a-zA-Z0-9_\-\.]+\s+modified|properties\s+of|inspect\s+file|tell\s+me\s+about\s+[a-zA-Z0-9_\-\.]+|about\s+[a-zA-Z0-9_\-\.]+\.[a-zA-Z0-9]+|metadata\s+of|how\s+big\s+is\s+[a-zA-Z0-9_\-\.]+\.[a-zA-Z0-9]+|when\s+was\s+this\s+file\s+created|file\s+details\s+for|file\s+information\s+for)\b", text):
            return "FILE_INFO", 0.92, {"path": entities.name_pattern or entities.path or ""}, []

        if re.search(r"\b(show\s+(?:the\s+)?(?:first|1|\d+)\s+\d+\s+lines|read\s+[a-zA-Z0-9_\-\.]+|display\s+server\.log|show\s+contents\s+of|read\s+first|view\s+readme|print\s+log\.txt|show\s+(?:the\s+)?top\s+\d+\s+lines|show\s+text\s+in|preview\s+server\.log|cat\s+[a-zA-Z0-9_\-\.]+|what\s+is\s+inside\s+[a-zA-Z0-9_\-\.]+|display\s+contents\s+of)\b", text):
            lines = entities.count or 30
            return "READ_TEXT_FILE", 0.90, {"path": entities.name_pattern or entities.path or "", "lines": lines}, []

        # --- ARCHIVES ---
        if re.search(r"\b(unzip|extract\s+model\.zip|extract\s+archive|uncompress|unpack|extract\s+files\s+from|extract\s+all\s+from|decompress|open\s+zip\s+archive)\b", text):
            return "EXTRACT_ARCHIVE", 0.92, {"target": entities.name_pattern or entities.path or "", "destination": entities.destination_path or ""}, []

        if re.search(r"\b(zip\s+my|create\s+archive|make\s+archive|compress\s+these\s+files|create\s+a\s+zip|zip\s+files|compress\s+folder|make\s+a\s+zip|package\s+documents\s+into\s+zip|zip\s+up|archive\s+[a-zA-Z0-9_\-\.\/\\]+|zip\s+[a-zA-Z0-9_\-\.\/\\]+)\b", text):
            return "CREATE_ARCHIVE", 0.92, {"target": entities.path or entities.name_pattern or ""}, []

        # --- PROCESS MANAGEMENT ---
        m_proc = re.search(r"\b(kill|terminate|stop|end|close)\s+(?:process\s+|pid\s+|task\s+)?([a-zA-Z0-9_\-\.]+)\b", text)
        if m_proc:
            cand = m_proc.group(2).lower()
            if cand not in {"the", "a", "all", "scan", "task", "files", "folder", "temporary", "temp", "job"}:
                if cand.isdigit():
                    return "TERMINATE_PROCESS", 0.95, {"pids": [int(cand)]}, []
                return "TERMINATE_PROCESS", 0.90, {"process_name": cand}, []

        if re.search(r"\b(stop\s+all\s+[a-zA-Z0-9_\-\.]+\s+processes)\b", text):
            return "TERMINATE_PROCESS", 0.90, {}, []

        if re.search(r"\b(top\s+(?:\d+\s+)?processes|highest\s+cpu\s+processes|top\s+cpu|processes\s+using\s+the\s+most\s+ram|eating\s+my\s+cpu|whats?\s+using\s+the\s+most\s+ram|what\s+is\s+using\s+the\s+most\s+ram|processes\s+taking\s+the\s+most\s+memory|program\s+is\s+using\s+the\s+most\s+cpu|top\s+memory|highest\s+memory\s+tasks|process\s+uses\s+the\s+most\s+resources|heaviest\s+processes|highest\s+cpu\s+load|top\s+\d+\s+cpu)\b", text):
            sort_by = "memory" if ("ram" in text or "memory" in text) else "cpu"
            return "TOP_PROCESSES", 0.95, {"sort_by": sort_by, "limit": entities.count or 10}, []

        if re.search(r"\b(using\s+port|listening\s+on\s+port|process\s+(?:running\s+)?on\s+port|check\s+port|who\s+is\s+using\s+port|on\s+port|inspect\s+port|app\s+is\s+listening\s+on\s+port|port\s+\d{2,5})\b", text):
            m = re.search(r"port\s+(\d+)", text)
            p = int(m.group(1)) if m else None
            return "PROCESS_BY_PORT", 0.95, {"port": p}, []

        if re.search(r"\b(is\s+[a-zA-Z0-9_\-\.]+\s+(?:running|active|open)|is\s+process\s+[a-zA-Z0-9_\-\.]+\s+active|check\s+(?:whether|if)\s+[a-zA-Z0-9_\-\.]+\s+is\s+(?:running|open|active)|find\s+(?:all\s+)?[a-zA-Z0-9_\-\.]+\s+processes|process\s+named\s+[a-zA-Z0-9_\-\.]+|locate\s+process\s+[a-zA-Z0-9_\-\.]+|look\s+for\s+process\s+[a-zA-Z0-9_\-\.]+|search\s+(?:for\s+)?(?:running\s+)?process\s+[a-zA-Z0-9_\-\.]+|find\s+process\s+[a-zA-Z0-9_\-\.]+)\b", text):
            m = re.search(r"(?:is|check\s+if|check\s+whether|find|locate|process\s+named|for\s+process)\s+([a-zA-Z0-9_\-\.]+)", text)
            cand = entities.process_name or (m.group(1).lower() if m else None)
            return "FIND_PROCESS", 0.92, {"name": cand or "process"}, []

        if re.search(r"\b(list\s+running\s+processes|list\s+processes|running\s+processes|ps\b|active\s+processes|running\s+tasks|display\s+running\s+tasks|what\s+processes\s+are\s+currently\s+running|list\s+all\s+tasks|process\s+list|running\s+programs|current\s+system\s+processes|open\s+processes|get\s+running\s+processes)\b", text):
            return "LIST_PROCESSES", 0.95, {"limit": entities.count or 50}, []

        if re.search(r"\b(running\s+in\s+the\s+background|background\s+tasks|list\s+active\s+tasks|what\s+tasks\s+are\s+running|view\s+background\s+jobs|check\s+task\s+progress|show\s+tasks|are\s+there\s+any\s+tasks|ongoing\s+tasks|current\s+background\s+tasks|what\s+jobs\s+are\s+active|tasks\s+status|active\s+background\s+jobs|view\s+running\s+tasks)\b", text):
            return "SHOW_TASKS", 0.95, {}, []

        # --- HARDWARE & SYSTEM METRICS ---
        if re.search(r"\b(how\s+long\s+has\s+my\s+pc\s+been\s+on|system\s+uptime|show\s+uptime|how\s+long\s+has\s+this\s+computer\s+been\s+running|check\s+system\s+uptime|computer\s+is\s+running|what\s+is\s+the\s+system\s+uptime|pc\s+uptime|how\s+long\s+since\s+last\s+reboot|when\s+was\s+the\s+computer\s+started|check\s+uptime|system\s+been\s+up|how\s+long\s+my\s+pc\s+is\s+running|uptime\b)\b", text):
            return "SHOW_UPTIME", 0.95, {}, []

        if re.search(r"\b(battery\s+level|check\s+battery|how\s+much\s+battery|battery\s+status|battery\s+percentage|is\s+my\s+laptop\s+charging|battery\s+charge|battery\s+health|battery\s+remaining|battery\s+info|battery\b)\b", text):
            return "SHOW_BATTERY", 0.95, {}, []

        if re.search(r"\b(what\s+os\s+am\s+i\s+on|operating\s+system|show\s+os\s+version|version\s+of\s+windows|linux\s+distribution|os\s+info|tell\s+me\s+my\s+os|my\s+os|os\s+version|which\s+os|platform\s+info|platform\s+information|what\s+is\s+my\s+operating\s+system|display\s+os\s+details)\b", text):
            return "SHOW_OS_INFO", 0.95, {}, []

        if re.search(r"\b(my\s+ip\s+address|network\s+interfaces|what\s+is\s+my\s+(?:local\s+)?ip|local\s+ip\s+address|network\s+configuration|display\s+ip|network\s+info|internal\s+ip|network\s+adapters|what\s+is\s+my\s+ip|check\s+my\s+ip|network\s+status|ip\s+address\s+info|list\s+network\s+interfaces)\b", text):
            return "SHOW_NETWORK", 0.95, {}, []

        if re.search(r"\b(how\s+hot\s+is\s+my\s+cpu|cpu\s+temperature|hardware\s+temperature|system\s+temperatures|cpu\s+overheating|thermal\s+status|show\s+temperatures|cpu\s+temp|temperature\s+of\s+my\s+computer|cpu\s+heat|system\s+thermals|hardware\s+temp|thermal\s+readings|how\s+hot\s+is\s+the\s+computer|display\s+temperatures)\b", text):
            return "SHOW_TEMPERATURES", 0.95, {}, []

        if re.search(r"\b(show\s+my\s+system\s+usage|system\s+usage|system\s+info|system\s+specs|specs\b|hardware\s+specifications|system\s+status|system\s+information|computer\s+specifications|system\s+overview|overall\s+system\s+stats|summary\s+of\s+system|full\s+system\s+status)\b", text):
            return "SYSTEM_INFO", 0.95, {"metric": "all"}, []

        if re.search(r"\b(show\s+my\s+ram\s+usage|ram\s+usage|memory\s+usage|how\s+much\s+ram|check\s+memory\s+consumption|how\s+much\s+ram\s+is\s+free|display\s+ram|available\s+memory|check\s+my\s+memory|ram\s+percentage|how\s+much\s+memory|view\s+memory|ram\s+stats|ram\s+status|memory\b|ram\b)\b", text):
            return "SHOW_MEMORY", 0.95, {"metric": "memory"}, []

        if re.search(r"\b(show\s+cpu\s+usage|cpu\s+usage|cpu\s+percent|processor\s+usage|processor\s+load|display\s+cpu\s+percentage|per-core\s+cpu|processor\s+performance|current\s+cpu\s+load|check\s+cpu\s+consumption|view\s+cpu\s+percent|how\s+busy\s+is\s+the\s+processor|cpu\s+stats|cpu\b)\b", text):
            per_core = "per-core" in text or "per core" in text
            return "SHOW_CPU", 0.95, {"metric": "cpu", "per_core": per_core}, []

        if (re.search(r"\b(show\s+disk\s+usage|disk\s+usage|disk\s+space|storage\s+on\s+root|free\s+space|disk\s+space\s+is\s+left|free\s+space\s+on\s+disk|display\s+disk\s+usage|how\s+full\s+is\s+my\s+hard\s+drive|available\s+disk\s+storage|view\s+storage\s+capacity|disk\s+space\s+for\s+drive|free\s+storage|storage\b)\b", text) or re.search(r"space\s+on\s+[a-zA-Z]:?", text)) and not re.search(r"\b(folder|directory|projects|downloads|documents|desktop)\b", text):
            drive_match = re.search(r"\b([a-zA-Z]:|\/)\b", raw_text)
            drive = drive_match.group(1) if drive_match else None
            return "SHOW_DISK", 0.95, {"metric": "disk", "target": drive}, []

        # --- FOLDER SIZE & LARGEST FOLDERS ---
        if re.search(r"\b(which\s+(?:folders|directories)\s+are\s+biggest|top\s+(?:\d+\s+)?(?:folders|directories)\s+by\s+size|biggest\s+(?:folders|directories)|largest\s+(?:folders|directories)|top\s+(?:folders|directories)\s+by\s+size|biggest\s+directories|heaviest\s+directories|directory\s+takes\s+the\s+most\s+space)\b", text):
            return "LARGEST_FOLDERS", 0.92, {"count": entities.count or 10, "path": entities.path or ""}, []

        if re.search(r"\b(how\s+big\s+is|size\s+of|space\s+is\s+[a-zA-Z0-9_\-\.\/\\]+\s+taking|calculate\s+size\s+of|measure\s+size\s+of|what\s+size\s+is\s+the|folder\s+size|how\s+much\s+storage\s+does\s+[a-zA-Z0-9_\-\.\/\\]+\s+use|check\s+how\s+big)\b", text):
            return "FOLDER_SIZE", 0.92, {"path": entities.path or ""}, []

        if re.search(r"\b(find\s+duplicate|duplicate\s+files|duplicates\b|scan\s+for\s+identical|detect\s+duplicate|search\s+for\s+duplicates|duplicate\s+photos|locate\s+duplicate|identify\s+duplicate|find\s+copy\s+files)\b", text):
            return "FIND_DUPLICATES", 0.95, {"path": entities.path or ""}, []

        if re.search(r"\b(empty\s+(?:folders|directories)|folders\s+with\s+no\s+files|zero-byte\s+folders|zero-item\s+directories|folders\s+are\s+empty)\b", text):
            return "FIND_EMPTY_FOLDERS", 0.92, {"path": entities.path or ""}, []

        if re.search(r"\b(how\s+many\s+photos|count\s+pdfs|how\s+many\s+files|count\s+all\s+files|number\s+of\s+files|how\s+many\s+images|count\s+videos|count\s+files|total\s+number\s+of\s+documents|how\s+many\s+items|count\s+python\s+files|how\s+many\s+files\s+are\s+there|number\s+of\s+pdfs|how\s+many\s+music\s+files)\b", text):
            return "COUNT_FILES", 0.92, {
                "path": entities.path or "",
                "file_type": entities.file_type or "",
                "extensions": list(entities.extensions),
            }, []

        # --- SUPERLATIVES ON FILES ---
        if re.search(r"\b(largest\s+file|biggest\s+file|biggest\s+files|largest\s+videos|what\s+is\s+taking\s+up\s+the\s+most\s+space|which\s+file\s+is\s+the\s+heaviest|biggest\s+\d+\s+files|top\s+(?:\d+\s+)?largest\s+files|heaviest\s+file|show\s+largest\s+file|largest\s+files)\b", text):
            count = entities.count or (1 if "largest file" in text or "biggest file" in text or "heaviest" in text else 10)
            return "LARGEST_FILES", 0.95, {
                "count": count,
                "path": entities.path or "",
                "file_type": entities.file_type or "",
                "extensions": list(entities.extensions),
            }, []

        if re.search(r"\b(smallest\s+\d+\s+images|smallest\s+file|smallest\s+files|smallest\s+\d+\s+files|what\s+is\s+the\s+smallest\s+file|tiny\s+files|which\s+file\s+is\s+the\s+smallest|display\s+smallest\s+files|smallest\s+documents)\b", text):
            count = entities.count or 10
            return "SMALLEST_FILES", 0.95, {
                "count": count,
                "path": entities.path or "",
                "file_type": entities.file_type or "",
                "extensions": list(entities.extensions),
            }, []

        if re.search(r"\b(newest\s+download|latest\s+files|newest\s+files|most\s+recent\s+files|latest\s+\d+\s+files|files\s+were\s+created\s+recently|latest\s+documents\s+modified|recently\s+modified\s+files|newest\s+downloads|find\s+the\s+newest\s+file|newest\s+\d+\s+files|recent\s+files)\b", text):
            count = entities.count or 10
            return "NEWEST_FILES", 0.95, {
                "count": count,
                "path": entities.path or "",
                "file_type": entities.file_type or "",
                "extensions": list(entities.extensions),
            }, []

        if re.search(r"\b(oldest\s+files|oldest\s+file|what\s+are\s+the\s+oldest\s+files|top\s+\d+\s+oldest\s+files|which\s+file\s+is\s+the\s+oldest|oldest\s+documents|oldest\s+\d+\s+files|oldest\s+file\s+on\s+my\s+system)\b", text):
            count = entities.count or 10
            return "OLDEST_FILES", 0.95, {
                "count": count,
                "path": entities.path or "",
                "file_type": entities.file_type or "",
                "extensions": list(entities.extensions),
            }, []

        # --- LIST FILES VS FIND FILES ---
        if re.search(r"\b(list\s+files\s+in|what\s+is\s+in\s+my|what\s+is\s+in\s+[a-zA-Z0-9_\-\.\/\\]+|show\s+this\s+folder|list\s+directory\s+contents|show\s+files\s+in|what\s+files\s+are\s+in|display\s+files\s+in|list\s+the\s+contents|view\s+files\s+in|browse\s+files|show\s+directory\s+listing|list\s+files|show\s+what\s+is\s+in)\b", text):
            return "LIST_FILES", 0.90, {"path": entities.path or ""}, []

        if re.search(r"\b(find\s+files|find\s+pdfs|find\s+files\s+named|large\s+files|find\s+all\s+images|search\s+for\s+documents|find\s+files\s+smaller|find\s+files\s+between|find\s+python\s+files|search\s+for\s+files|search\s+for\s+pdfs|find\s+all\s+logs|find\s+files\s+older|search\s+for\s+images)\b", text):
            return "FIND_FILES", 0.90, {
                "path": entities.path or "",
                "pattern": entities.name_pattern or "",
                "min_size_bytes": entities.min_size_bytes,
                "max_size_bytes": entities.max_size_bytes,
                "time_cutoff": entities.time_cutoff_seconds,
                "file_type": entities.file_type or "",
                "extensions": list(entities.extensions),
            }, []

        return None, 0.0, {}, []

    def _get_intent_risk(self, intent_name: str) -> RiskLevel:
        from shellsense.safety.classifier import classify_risk
        return classify_risk(intent_name)

    def _format_intent_name(self, intent_name: str) -> str:
        return intent_name.replace("_", " ").title()

    def _get_closest_suggestions(self, text: str) -> list[str]:
        scored = []
        for suggestion in _CATALOGUE_SUGGESTIONS:
            score = fuzz.token_set_ratio(text, suggestion.lower())
            scored.append((score, suggestion))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [s[1] for s in scored[:4]]


# Global singleton parser
DEFAULT_PARSER = RuleBasedParser()
