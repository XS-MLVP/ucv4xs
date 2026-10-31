"""Drive persistent signal levels without consuming a clock edge.

``ClockedWriteDriver`` waits at least one cycle per transaction. For DUTs
whose reference model advances per edge, such a hidden cycle silently
desynchronises expectations from the RTL. This driver only writes the level and
returns immediately; the caller owns the clocking policy.
"""

from __future__ import annotations

from typing import Any
from typing import Mapping

from toffee.data import drive_data

from suites.frontend.icache.ports.bindings import PortBinding


class LevelDriver:
    """Write a level immediately; no edge is consumed or awaited."""

    def __init__(self, binding: PortBinding) -> None:
        self.binding = binding
        self._closed = False

    def set(self, values: Mapping[str, Any]) -> None:
        if self._closed:
            raise RuntimeError(f"{self.binding.name}: level driver is closed")
        drive_data(self.binding.bits, values, self.binding.name)

    def close(self) -> None:
        self._closed = True
