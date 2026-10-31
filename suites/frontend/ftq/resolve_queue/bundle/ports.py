"""ResolveQueue port binding over generated flat pins."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from suites.frontend.ftq.ports import Pins
from suites.frontend.ftq.harness import Dut


LANE_FIELDS = {
    "index_flag": "bits_ftqIdx_flag",
    "index": "bits_ftqIdx_value",
    "offset": "bits_ftqOffset",
    "pc": "bits_pc_addr",
    "target": "bits_target_addr",
    "taken": "bits_taken",
    "mispredict": "bits_mispredict",
    "branch_type": "bits_attribute_branchType",
    "ras_action": "bits_attribute_rasAction",
}


def lane_pins(dut: Dut, prefix: str, *, name: str) -> Pins:
    names = {logical: prefix + field for logical, field in LANE_FIELDS.items()}
    names["valid"] = prefix + "valid"
    return Pins(dut, names, name=name)


def train_output_pins(dut: Dut) -> Pins:
    names = {
        "valid": "io_bpuTrain_valid",
        "ready": "io_bpuTrain_ready",
        "index_flag": "io_bpuTrain_bits_ftqIdx_flag",
        "index": "io_bpuTrain_bits_ftqIdx_value",
        "start_pc": "io_bpuTrain_bits_startPc_addr",
    }
    for slot in range(8):
        base = f"io_bpuTrain_bits_branches_{slot}_"
        for field in ("valid", "bits_target_addr", "bits_taken",
                      "bits_cfiPosition", "bits_attribute_branchType",
                      "bits_attribute_rasAction", "bits_mispredict"):
            names[f"slot{slot}.{field}"] = base + field
    return Pins(dut, names, name="resolve_queue.train")


@dataclass(frozen=True)
class ResolveQueuePorts:
    backend: tuple[Pins, Pins, Pins]
    ifu: Pins
    train: Pins
    redirect: Pins
    enqueue: Pins

    @classmethod
    def bind(cls, dut: Dut) -> "ResolveQueuePorts":
        backend = tuple(
            lane_pins(dut, f"io_backendResolve_{lane}_", name=f"resolve_queue.backend{lane}")
            for lane in range(3)
        )
        ifu = lane_pins(dut, "io_ifuResolve_", name="resolve_queue.ifu")
        train = train_output_pins(dut)
        redirect = Pins(dut, {
            "valid": "io_backendRedirect",
            "flag": "io_backendRedirectPtr_flag",
            "value": "io_backendRedirectPtr_value",
        }, name="resolve_queue.redirect")
        enqueue = Pins(dut, {
            "valid": "io_bpuEnqueue",
            "value": "io_bpuEnqueuePtr_value",
        }, name="resolve_queue.enqueue")
        return cls(backend, ifu, train, redirect, enqueue)
