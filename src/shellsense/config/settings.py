"""Configuration and settings loader for ShellSense.

Invariant 20: Settings can tighten but never widen what a consent grant allows,
and cannot remove hard-coded deny rules.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import platformdirs
from pydantic import BaseModel, ConfigDict, Field


class Settings(BaseModel):
    """Runtime configuration model."""
    model_config = ConfigDict(frozen=True)

    allowed_roots: list[str] = Field(default_factory=list)
    denied_paths: list[str] = Field(default_factory=list)
    bulk_item_limit: int = 100
    plan_expiry_seconds: int = 120
    task_concurrency: int = 2
    confidence_threshold: float = 0.7
    log_max_bytes: int = 10 * 1024 * 1024  # 10 MB
    log_backup_count: int = 5


def get_config_dir() -> Path:
    """Return user configuration directory outside of any git repository."""
    return Path(platformdirs.user_config_dir("shellsense", appauthor=False))


def load_settings(custom_path: Path | None = None) -> Settings:
    """Load default settings combined with optional user overrides.

    Falls back to restrictive defaults on missing or corrupted configuration.
    """
    default_file = Path(__file__).parent / "default_settings.json"
    defaults: dict[str, Any] = {}
    if default_file.exists():
        try:
            defaults = json.loads(default_file.read_text(encoding="utf-8"))
        except Exception:
            defaults = {}

    user_settings_file = custom_path or (get_config_dir() / "settings.json")
    user_overrides: dict[str, Any] = {}
    if user_settings_file.exists():
        try:
            user_overrides = json.loads(user_settings_file.read_text(encoding="utf-8"))
        except Exception:
            # Fall back to defaults on unparseable/corrupted settings
            user_overrides = {}

    merged = {**defaults, **user_overrides}

    # Ensure limits remain restrictive
    bulk_limit = min(int(merged.get("bulk_item_limit", 100)), 500)
    plan_expiry = max(10, min(int(merged.get("plan_expiry_seconds", 120)), 600))
    concurrency = max(1, min(int(merged.get("task_concurrency", 2)), 8))
    confidence = max(0.5, min(float(merged.get("confidence_threshold", 0.7)), 0.99))

    return Settings(
        allowed_roots=list(merged.get("allowed_roots", [])),
        denied_paths=list(merged.get("denied_paths", [])),
        bulk_item_limit=bulk_limit,
        plan_expiry_seconds=plan_expiry,
        task_concurrency=concurrency,
        confidence_threshold=confidence,
        log_max_bytes=int(merged.get("log_max_bytes", 10 * 1024 * 1024)),
        log_backup_count=int(merged.get("log_backup_count", 5)),
    )
