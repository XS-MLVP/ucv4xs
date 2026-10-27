"""bpuverify.abtb.bundle.ports components."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from toffee import Bundle
from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.common.bundle.bindings import PulseBinding
from bpuverify.common.bundle.bindings import bind_bundle
from bpuverify.common.bundle.bindings import bind_pulse


@dataclass(frozen=True, slots=True)
class AbtbPorts:
    control: PortBinding
    lookup: PortBinding
    training: PulseBinding
    prediction: PortBinding
    status: PortBinding

    @classmethod
    def bind(cls, dut: Any) -> "AbtbPorts":
        io = bound_io = bind_bundle(dut, ("io",), name="abtb.io").bits
        control = PortBinding(dut.clock, Bundle(enable=io.enable), "abtb.control")
        lookup = PortBinding(
            dut.clock,
            Bundle(
                s0_fire=io.stageCtrl.s0_fire,
                s1_fire=io.stageCtrl.s1_fire,
                s2_fire=io.stageCtrl.s2_fire,
                s3_fire=io.stageCtrl.s3_fire,
                start_pc=io.startPc_addr,
                new_start_pc=io.newStartPc_addr,
                # AbtbHashFhInfo reuses folded PHR entry 2; RTL hashes its low 4 bits.
                path_hash=io.normalPathHist_hist[2].foldedHist,
                s2_override=io.bpuS2Override,
                s3_override=io.bpuS3Override,
                override_start_pc=io.overrideStartPc_addr,
                redirect=io.redirect,
            ),
            "abtb.lookup",
        )
        full_train = bind_pulse(dut, ("io", "fastTrain"), name="abtb.fast_train")
        train_bits = full_train.bits.view_as(
            {
                "start_pc": "startPc_addr",
                "meta": "abtbMeta",
                "branch": {
                    "target": "branch.target_addr",
                    "taken": "branch.taken",
                    "position": "branch.cfiPosition",
                    "branch_type": "branch.attribute.branchType",
                    "ras_action": "branch.attribute.rasAction",
                    "mispredict": "branch.mispredict",
                },
            },
            path="abtb.fast_train.bits",
        )
        training = PulseBinding(
            full_train.clock, full_train.valid, train_bits, full_train.name
        )
        prediction = PortBinding(
            dut.clock,
            Bundle(
                entries=bound_io.result_entries,
                meta=bound_io.meta,
                micro_tage=bound_io.toMicroTage,
            ),
            "abtb.prediction",
        )
        status = PortBinding(
            dut.clock,
            Bundle(reset_done=io.sramResetDone, train_ready=io.trainReady),
            "abtb.status",
        )
        return cls(control, lookup, training, prediction, status)
