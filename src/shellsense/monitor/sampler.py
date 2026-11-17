"""Hardware performance resource sampler and ring buffer.

Collects CPU, RAM, and Disk metrics at 1 Hz for the System Monitor screen.
"""

from __future__ import annotations

import collections
import contextlib
import os
import threading
import time
from pathlib import Path

import psutil
from pydantic import BaseModel, ConfigDict

from shellsense.platform import get_platform_adapter


class SystemSample(BaseModel):
    """Single hardware resource metric sample."""
    model_config = ConfigDict(frozen=True)

    timestamp: float
    cpu_percent: float
    ram_used_bytes: int
    ram_total_bytes: int
    ram_percent: float
    disk_used_bytes: int
    disk_total_bytes: int
    disk_percent: float


class MetricRingBuffer:
    """Thread-safe ring buffer storing recent system performance samples."""

    def __init__(self, max_samples: int = 600) -> None:
        self.max_samples = max_samples
        self._samples: collections.deque[SystemSample] = collections.deque(maxlen=max_samples)
        self._lock = threading.Lock()

    def add_sample(self, sample: SystemSample) -> None:
        with self._lock:
            self._samples.append(sample)

    def get_latest(self) -> SystemSample | None:
        with self._lock:
            return self._samples[-1] if self._samples else None

    def get_history(self, range_seconds: int = 600) -> list[SystemSample]:
        with self._lock:
            cutoff = time.time() - range_seconds
            return [s for s in self._samples if s.timestamp >= cutoff]


class SystemSampler:
    """Background hardware resource sampler."""

    def __init__(self, ring_buffer: MetricRingBuffer | None = None) -> None:
        self.ring_buffer = ring_buffer or MetricRingBuffer()
        self._running = False
        self._thread: threading.Thread | None = None
        self.adapter = get_platform_adapter()

    def sample_now(self) -> SystemSample:
        """Capture an immediate system snapshot."""
        now = time.time()
        cpu_pct = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        root_path = Path.home().anchor or ("C:\\" if os.name == "nt" else "/")
        try:
            disk = psutil.disk_usage(root_path)
        except Exception:
            disk = psutil.disk_usage("/")

        sample = SystemSample(
            timestamp=now,
            cpu_percent=cpu_pct,
            ram_used_bytes=mem.used,
            ram_total_bytes=mem.total,
            ram_percent=mem.percent,
            disk_used_bytes=disk.used,
            disk_total_bytes=disk.total,
            disk_percent=disk.percent,
        )
        self.ring_buffer.add_sample(sample)
        return sample

    def start(self) -> None:
        """Start background 1 Hz sampling loop."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop sampling loop."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.5)

    def _loop(self) -> None:
        while self._running:
            with contextlib.suppress(Exception):
                self.sample_now()
            time.sleep(1.0)


DEFAULT_SAMPLER = SystemSampler()
