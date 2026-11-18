"""Entity extraction and normalization for ShellSense NLP parser.

Handles normalization, filler stripping, number-to-digit conversion,
size/count parsing, time ranges, file type mappings, path resolution, and process entities.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from shellsense.safety.sanitize import sanitize_text

# Filler words/phrases to strip during normalization
_FILLER_PATTERNS = [
    re.compile(r"\b(please|can you|could you|would you|i want to|i need to|hey shellsense|shellsense)\b", re.IGNORECASE),
    re.compile(r"\b(tell me|show me|help me to|help me|kindly|just)\b", re.IGNORECASE),
]

# Common English contractions
_CONTRACTIONS: dict[str, str] = {
    "what's": "what is",
    "whats": "what is",
    "can't": "cannot",
    "cant": "cannot",
    "don't": "do not",
    "dont": "do not",
    "didn't": "did not",
    "didnt": "did not",
    "won't": "will not",
    "wont": "will not",
    "it's": "it is",
    "how's": "how is",
    "there's": "there is",
    "where's": "where is",
    "let's": "let us",
}

# Number words to digits
_NUMBER_WORDS: dict[str, int] = {
    "zero": 0,
    "one": 1,
    "first": 1,
    "two": 2,
    "second": 2,
    "three": 3,
    "third": 3,
    "four": 4,
    "fourth": 4,
    "five": 5,
    "fifth": 5,
    "six": 6,
    "sixth": 6,
    "seven": 7,
    "seventh": 7,
    "eight": 8,
    "eighth": 8,
    "nine": 9,
    "ninth": 9,
    "ten": 10,
    "tenth": 10,
    "eleven": 11,
    "twelve": 12,
    "twenty": 20,
    "thirty": 30,
    "fifty": 50,
    "hundred": 100,
    "a few": 5,
    "couple": 2,
}

# File type groups mapped to canonical extensions
FILE_TYPE_GROUPS: dict[str, set[str]] = {
    "pdf": {".pdf"},
    "pdfs": {".pdf"},
    "document": {".pdf", ".docx", ".doc", ".txt", ".rtf", ".odt", ".md"},
    "documents": {".pdf", ".docx", ".doc", ".txt", ".rtf", ".odt", ".md"},
    "spreadsheet": {".xlsx", ".xls", ".csv", ".ods"},
    "spreadsheets": {".xlsx", ".xls", ".csv", ".ods"},
    "image": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"},
    "images": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"},
    "photo": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"},
    "photos": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"},
    "video": {".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv", ".webm"},
    "videos": {".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv", ".webm"},
    "music": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"},
    "audio": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"},
    "archive": {".zip", ".tar", ".gz", ".7z", ".rar", ".tar.gz", ".bz2"},
    "archives": {".zip", ".tar", ".gz", ".7z", ".rar", ".tar.gz", ".bz2"},
    "code": {".py", ".ts", ".tsx", ".js", ".jsx", ".html", ".css", ".json", ".c", ".cpp", ".rs", ".go", ".java"},
    "log": {".log"},
    "logs": {".log"},
    "installer": {".exe", ".msi", ".dmg", ".deb", ".rpm", ".appimage"},
    "installers": {".exe", ".msi", ".dmg", ".deb", ".rpm", ".appimage"},
}


@dataclass
class ExtractedEntities:
    """Entities extracted from normalized text."""
    count: int | None = None
    min_size_bytes: int | None = None
    max_size_bytes: int | None = None
    superlative: str | None = None  # largest, smallest, newest, oldest, most_ram, most_cpu
    time_cutoff_seconds: float | None = None  # mtime cutoff
    time_label: str | None = None
    file_type: str | None = None
    extensions: set[str] = field(default_factory=set)
    name_pattern: str | None = None
    path: str | None = None
    destination_path: str | None = None
    pid: int | None = None
    pids: list[int] = field(default_factory=list)
    process_name: str | None = None
    port: int | None = None
    is_negated: bool = False
    context_ref: str | None = None  # "them", "those", "first 3", "largest one"


def normalize_text(text: str) -> str:
    """Normalize input text: clean control chars, expand contractions, convert number words."""
    cleaned = sanitize_text(text).strip()
    if not cleaned:
        return ""

    lowered = cleaned.lower()

    # Expand contractions
    for contr, expansion in _CONTRACTIONS.items():
        lowered = re.sub(rf"\b{contr}\b", expansion, lowered)

    # Convert phrase numbers first (e.g. "a few")
    for phrase, num in _NUMBER_WORDS.items():
        if " " in phrase:
            lowered = re.sub(rf"\b{phrase}\b", str(num), lowered)

    # Strip conversational filler words
    for pat in _FILLER_PATTERNS:
        lowered = pat.sub(" ", lowered)

    # Convert single number words to digits
    for word, num in _NUMBER_WORDS.items():
        if " " not in word:
            lowered = re.sub(rf"\b{word}\b", str(num), lowered)

    # Collapse multiple whitespace
    return re.sub(r"\s+", " ", lowered).strip()


def check_negation(text: str) -> bool:
    """Check if the request expresses negative command (don't delete, do not remove, never)."""
    negation_patterns = [
        re.compile(r"\b(do not|dont|don't|never|stop|refrain from)\s+(delete|remove|kill|trash|terminate|clean)", re.IGNORECASE),
        re.compile(r"\b(do not|dont|don't)\s+(touch|modify|change)", re.IGNORECASE),
    ]
    return any(p.search(text) for p in negation_patterns)


def extract_entities(text: str, original_text: str = "") -> ExtractedEntities:
    """Extract structured entities from normalized text."""
    entities = ExtractedEntities()
    entities.is_negated = check_negation(original_text or text)

    # 1. Superlatives & Counts
    if re.search(r"\b(largest|biggest|heaviest|most space|taking up the most)\b", text):
        entities.superlative = "largest"
    elif re.search(r"\b(smallest|tiniest|tiny)\b", text):
        entities.superlative = "smallest"
    elif re.search(r"\b(newest|latest|most recent|recently created|recently modified)\b", text):
        entities.superlative = "newest"
    elif re.search(r"\b(oldest)\b", text):
        entities.superlative = "oldest"
    elif re.search(r"\b(most ram|most memory|highest memory|highest ram)\b", text):
        entities.superlative = "most_ram"
    elif re.search(r"\b(most cpu|eating my cpu|highest cpu)\b", text):
        entities.superlative = "most_cpu"

    # Count extraction (e.g. "top 5", "biggest 10", "the largest file" -> 1)
    count_match = re.search(r"\b(?:top|first|last|biggest|largest|smallest|newest|oldest)?\s*(\d+)\s*(?:files|folders|processes|items|videos|photos|images|documents)?\b", text)
    if count_match and count_match.group(1):
        entities.count = int(count_match.group(1))
    elif re.search(r"\b(?:the|a)?\s*(largest|biggest|smallest|newest|oldest)\s+(?:file|folder|download|document|image|video)\b", text):
        # Singular superlative implies count=1
        entities.count = 1

    # 2. Size extraction (e.g. "over 1GB", "larger than 500MB", "smaller than 10MB")
    range_match = re.search(r"between\s+(\d+(?:\.\d+)?\s*[kmgt]?b)\s+and\s+(\d+(?:\.\d+)?\s*[kmgt]?b)", text, re.IGNORECASE)
    if range_match:
        entities.min_size_bytes = _parse_bytes(range_match.group(1))
        entities.max_size_bytes = _parse_bytes(range_match.group(2))
    else:
        over_match = re.search(r"(?:over|larger than|greater than|at least|bigger than|more than)\s+(\d+(?:\.\d+)?\s*[kmgt]?b)", text, re.IGNORECASE)
        if over_match:
            entities.min_size_bytes = _parse_bytes(over_match.group(1))

        under_match = re.search(r"(?:under|smaller than|less than|at most)\s+(\d+(?:\.\d+)?\s*[kmgt]?b)", text, re.IGNORECASE)
        if under_match:
            entities.max_size_bytes = _parse_bytes(under_match.group(1))

        if entities.min_size_bytes is None and entities.max_size_bytes is None:
            # Standalone size like "files 1 GB"
            standalone = re.search(r"\b(\d+(?:\.\d+)?\s*(?:gb|mb|kb|gigs|gigabytes|megabytes))\b", text, re.IGNORECASE)
            if standalone:
                entities.min_size_bytes = _parse_bytes(standalone.group(1))

    # 3. Time range extraction
    now = datetime.now(UTC)
    if "today" in text:
        cutoff = datetime(now.year, now.month, now.day, tzinfo=UTC).timestamp()
        entities.time_cutoff_seconds = cutoff
        entities.time_label = "today"
    elif "yesterday" in text:
        cutoff = (datetime(now.year, now.month, now.day, tzinfo=UTC) - timedelta(days=1)).timestamp()
        entities.time_cutoff_seconds = cutoff
        entities.time_label = "yesterday"
    elif "this week" in text:
        cutoff = (now - timedelta(days=7)).timestamp()
        entities.time_cutoff_seconds = cutoff
        entities.time_label = "this week"
    else:
        older_match = re.search(r"older than\s+(\d+)\s*(days|day|weeks|week|months|month|hours|hour)", text)
        if older_match:
            val = int(older_match.group(1))
            unit = older_match.group(2).lower()
            if "day" in unit:
                dt = timedelta(days=val)
            elif "week" in unit:
                dt = timedelta(weeks=val)
            elif "month" in unit:
                dt = timedelta(days=val * 30)
            else:
                dt = timedelta(hours=val)
            entities.time_cutoff_seconds = (now - dt).timestamp()
            entities.time_label = f"older than {val} {unit}"

    # 4. File types and extensions
    for type_name, ext_set in FILE_TYPE_GROUPS.items():
        if re.search(rf"\b{type_name}\b", text):
            entities.file_type = type_name
            entities.extensions.update(ext_set)

    # Literal extension in text (e.g. ".txt", ".pdf", "python files")
    ext_match = re.findall(r"\.([a-zA-Z0-9]{1,10})\b", text)
    for ext in ext_match:
        entities.extensions.add(f".{ext.lower()}")
    if "python files" in text or "python script" in text:
        entities.extensions.add(".py")

    # 5. Names and patterns: quoted or "named X", "called X", "containing X"
    quoted = re.findall(r"['\"]([^'\"]+)['\"]", original_text or text)
    if quoted:
        entities.name_pattern = quoted[0]

    named_match = re.search(r"(?:named|called|with name)\s+([a-zA-Z0-9_\-\.\*]+)", text)
    if named_match and not entities.name_pattern:
        entities.name_pattern = named_match.group(1)

    containing_match = re.search(r"(?:containing|contains|with text)\s+['\"]?([^'\"\n]+)['\"]?", text)
    if containing_match and not entities.name_pattern:
        entities.name_pattern = containing_match.group(1).strip()

    # 6. Location aliases and paths
    entities.path = _resolve_path_entity(text, original_text)

    # Destination path if "move X to Y" or "copy X to Y"
    to_match = re.search(r"\bto\s+([a-zA-Z0-9_\-\.\/\\:]+)", text)
    if to_match and entities.path:
        dest_candidate = to_match.group(1).strip()
        entities.destination_path = _resolve_named_path(dest_candidate)

    # 7. Processes, PIDs, Ports
    port_match = re.search(r"(?:port\s+|:)(\d{2,5})\b", text)
    if port_match:
        entities.port = int(port_match.group(1))

    pid_match = re.search(r"\b(?:pid|process)\s+(\d+)\b", text)
    if pid_match:
        entities.pid = int(pid_match.group(1))
        entities.pids.append(entities.pid)

    # Process names
    proc_match = re.search(r"(?:kill|terminate|stop|find|is|search|close)\s+(?:process\s+)?([a-zA-Z0-9_\-\.]+)(?:\s+running|\s+active)?", text)
    if proc_match:
        cand = proc_match.group(1).lower()
        if cand not in {"process", "pid", "all", "the", "my", "this", "files", "temporary"}:
            entities.process_name = cand

    # 8. Context reference ("delete them", "move those", "zip the first 3")
    if re.search(r"\b(them|those|these files|these photos|these items|the first \d+|the largest one)\b", text):
        ref_match = re.search(r"\b(them|those|these files|these photos|these items|the first \d+|the largest one)\b", text)
        entities.context_ref = ref_match.group(1) if ref_match else "them"

    return entities


def _parse_bytes(size_str: str) -> int:
    """Parse size strings like '1gb', '1.5 gigs', '500 mb', '100kb' into bytes."""
    clean = size_str.lower().replace(" ", "").replace("bytes", "").replace("gigabytes", "gb").replace("megabytes", "mb").replace("gigs", "gb")
    match = re.search(r"(\d+(?:\.\d+)?)\s*([kmgt]?b?)", clean)
    if not match:
        return 0
    val = float(match.group(1))
    unit = match.group(2)
    if "t" in unit:
        return int(val * 1024 * 1024 * 1024 * 1024)
    if "g" in unit:
        return int(val * 1024 * 1024 * 1024)
    if "m" in unit:
        return int(val * 1024 * 1024)
    if "k" in unit:
        return int(val * 1024)
    return int(val)


def _resolve_named_path(name: str) -> str:
    """Map standard folder aliases to OS path or resolve relative path."""
    clean = name.strip()
    home = Path.home()
    aliases = {
        "downloads": home / "Downloads",
        "documents": home / "Documents",
        "desktop": home / "Desktop",
        "pictures": home / "Pictures",
        "music": home / "Music",
        "videos": home / "Videos",
        "home": home,
        "backup": home / "Backup",
        "projects": home / "Projects",
    }
    lower = clean.lower()
    if lower in aliases:
        return str(aliases[lower])
    return clean


def _resolve_path_entity(text: str, original_text: str) -> str | None:
    """Extract and resolve folder or file path from text."""
    # Check for absolute path (Linux or Windows)
    win_match = re.search(r"([a-zA-Z]:\\[a-zA-Z0-9_\-\.\\]+)", original_text or text)
    if win_match:
        return win_match.group(1)

    linux_match = re.search(r"(\/(?:home|tmp|var|usr|etc)[a-zA-Z0-9_\-\.\/]*)", original_text or text)
    if linux_match:
        return linux_match.group(1)

    # Check for "this folder" / "current folder" / "here"
    if re.search(r"\b(this folder|current folder|here|this directory)\b", text):
        return str(Path.cwd())

    # Check standard aliases: in Downloads, in Documents, etc.
    in_alias = re.search(r"\b(?:in|from|of|for|into)\s+(downloads|documents|desktop|pictures|music|videos|projects|backup|home)\b", text)
    if in_alias:
        return _resolve_named_path(in_alias.group(1))

    # Bare alias mentioned
    for alias in ["downloads", "documents", "desktop", "pictures", "music", "videos"]:
        if re.search(rf"\b{alias}\b", text):
            return _resolve_named_path(alias)

    return None
