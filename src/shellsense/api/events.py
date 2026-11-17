"""WebSocket event hub with sequence IDs and client resume support.

Section 10: WebSocket messages carry sequence IDs; clients can resume from the
last ID upon reconnect. Server immediately drops unauthenticated clients.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import WebSocket


class EventHub:
    """Thread-safe event broadcaster with monotonic sequence IDs and resume buffer."""

    def __init__(self, buffer_size: int = 1000) -> None:
        self.buffer_size = buffer_size
        self._connections: set[WebSocket] = set()
        self._seq_id: int = 0
        self._history: list[dict[str, Any]] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(websocket)

    async def broadcast(self, event_type: str, data: dict[str, Any]) -> None:
        """Broadcast a sequenced event to all active WebSocket clients."""
        async with self._lock:
            self._seq_id += 1
            payload = {
                "seq_id": self._seq_id,
                "event": event_type,
                "data": data,
            }
            self._history.append(payload)
            if len(self._history) > self.buffer_size:
                self._history.pop(0)

            disconnected: list[WebSocket] = []
            for ws in self._connections:
                try:
                    await ws.send_text(json.dumps(payload))
                except Exception:
                    disconnected.append(ws)

            for ws in disconnected:
                self._connections.discard(ws)

    async def replay_since(self, websocket: WebSocket, last_seq_id: int) -> None:
        """Replay missed events upon client reconnection."""
        async with self._lock:
            missed = [msg for msg in self._history if msg["seq_id"] > last_seq_id]
            for msg in missed:
                try:
                    await websocket.send_text(json.dumps(msg))
                except Exception:
                    break


GLOBAL_EVENT_HUB = EventHub()
