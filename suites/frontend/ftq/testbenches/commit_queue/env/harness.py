"""CommitQueue transport: its agent owns the SDK full-input slots and phases."""

from __future__ import annotations

from pathlib import Path

from suites.frontend.ftq.testbenches.shared.env.harness import Dut


class CommitQueueDutHarness(Dut):
    """Disable the shared cycle-slot stream; do not add a second pause owner."""

    def __init__(self, name: str, coverage_path: Path | None) -> None:
        super().__init__(name, coverage_path, cycle_slots=False)
