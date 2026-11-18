"""System hardware monitor and metrics endpoints."""

from __future__ import annotations

import getpass
from typing import Any

from fastapi import APIRouter

from shellsense.monitor.sampler import DEFAULT_SAMPLER
from shellsense.platform import get_platform_adapter

router = APIRouter(tags=["system"])


@router.get("/system/info")
async def get_system_info() -> dict[str, Any]:
    adapter = get_platform_adapter()
    sample = DEFAULT_SAMPLER.sample_now()
    os_info = adapter.get_os_info()
    return {
        "user": getpass.getuser(),
        "os": {
            "system": os_info.system,
            "release": os_info.release,
            "display_name": os_info.display_name,
            "machine": os_info.machine,
        },
        "sample": sample.model_dump(),
    }


@router.get("/monitor/history")
async def get_monitor_history(range_seconds: int = 600) -> dict[str, Any]:
    samples = DEFAULT_SAMPLER.ring_buffer.get_history(range_seconds=range_seconds)
    return {"samples": [s.model_dump() for s in samples]}
