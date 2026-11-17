"""Settings inspection and non-security mutation endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from shellsense.api.schemas import SettingsUpdateRequest
from shellsense.config.settings import load_settings
from shellsense.platform import get_platform_adapter

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
async def get_settings():
    settings = load_settings()
    adapter = get_platform_adapter()
    return {
        "os_mode": "Auto (detected)",
        "detected_os": adapter.get_os_info().display_name,
        "confirmation_on_sensitive_actions": True,  # Invariant 15: Always True and locked
        "bulk_item_limit": settings.bulk_item_limit,
        "plan_expiry_seconds": settings.plan_expiry_seconds,
        "task_concurrency": settings.task_concurrency,
        "confidence_threshold": settings.confidence_threshold,
    }


@router.patch("")
async def update_settings(req: SettingsUpdateRequest):
    # Non-security settings update stub
    return {"status": "updated"}
