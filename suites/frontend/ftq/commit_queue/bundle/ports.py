"""CommitQueue port binding over generated flat pins."""

from __future__ import annotations

from dataclasses import dataclass

from suites.frontend.ftq.ports import Pins
from suites.frontend.ftq.harness import Dut


def commit_lane(dut: Dut, lane: int) -> Pins:
    prefix = f"io_backendCommit_{lane}_"
    return Pins(dut, {
        "valid": prefix + "valid",
        "ras": prefix + "bits_rasAction",
        "ptr": prefix + "bits_ftqPtr_value",
    }, name=f"commit_queue.backend{lane}")


@dataclass(frozen=True)
class CommitQueuePorts:
    backend: tuple[Pins, ...]
    train: Pins

    @classmethod
    def bind(cls, dut: Dut, width: int = 8) -> "CommitQueuePorts":
        backend = tuple(commit_lane(dut, lane) for lane in range(width))
        train = Pins(dut, {
            "valid": "io_bpuTrain_valid",
            "ras": "io_bpuTrain_bits_rasAction",
            "ptr": "io_bpuTrain_bits_ftqPtr_value",
        }, name="commit_queue.train")
        return cls(backend, train)
