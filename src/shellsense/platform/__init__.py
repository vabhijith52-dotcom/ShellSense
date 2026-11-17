"""Platform factory for ShellSense."""

import sys

from shellsense.platform.base import OSInfo, PlatformAdapter
from shellsense.platform.linux import LinuxAdapter
from shellsense.platform.windows import WindowsAdapter

_CURRENT_ADAPTER: PlatformAdapter | None = None


def get_platform_adapter() -> PlatformAdapter:
    """Return the singleton platform adapter appropriate for the current host OS."""
    global _CURRENT_ADAPTER
    if _CURRENT_ADAPTER is None:
        if sys.platform.startswith("win"):
            _CURRENT_ADAPTER = WindowsAdapter()
        else:
            _CURRENT_ADAPTER = LinuxAdapter()
    return _CURRENT_ADAPTER


__all__ = ["OSInfo", "PlatformAdapter", "get_platform_adapter"]
