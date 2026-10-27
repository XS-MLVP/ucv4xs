"""bpuverify.mbtb.bundle.ports components."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from toffee import Bundle
from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.common.bundle.bindings import PulseBinding
from bpuverify.common.bundle.bindings import bind_bundle


@dataclass(frozen=True, slots=True)
class MbtbPorts:
    control: PortBinding
    lookup: PortBinding
    training: PulseBinding
    prediction: PortBinding
    status: PortBinding

    @classmethod
    def bind(cls, dut: Any) -> "MbtbPorts":
        io = bound_io = bind_bundle(dut, ("io",), name="mbtb.io").bits
        control = PortBinding(
            dut.clock, Bundle(enable=io.enable), "mbtb.control"
        )
        lookup = PortBinding(
            dut.clock,
            Bundle(
                s0_fire=io.stageCtrl.s0_fire,
                s1_fire=io.stageCtrl.s1_fire,
                s2_fire=io.stageCtrl.s2_fire,
                s3_fire=io.stageCtrl.s3_fire,
                victim_taken=(io.s3_takenMask[4], io.s3_takenMask[9]),
                start_pc=io.startPc_addr,
            ),
            "mbtb.lookup",
        )

        training = PulseBinding(
            dut.clock,
            io.stageCtrl.t0_fire,
            Bundle(
                start_pc0=io.train.startPcVec_dup[0][0].addr,
                start_pc1=io.train.startPcVec_dup[0][1].addr,
                meta_entries=bound_io.train.meta.mbtb_entries,
                branches=tuple(
                    Bundle(
                        valid=branch.valid,
                        target=branch.bits.target_addr,
                        taken=branch.bits.taken,
                        position=branch.bits.cfiPosition,
                        branch_type=branch.bits.attribute.branchType,
                        ras_action=branch.bits.attribute.rasAction,
                        mispredict=branch.bits.mispredict,
                    )
                    for branch in io.train.branches
                ),
            ),
            "mbtb.training",
        )

        prediction = PortBinding(
            dut.clock,
            Bundle(
                entries=bound_io.result,
                meta_entries=bound_io.meta_entries,
            ),
            "mbtb.prediction",
        )
        status = PortBinding(
            dut.clock,
            Bundle(reset_done=io.sramResetDone, train_ready=io.trainReady),
            "mbtb.status",
        )
        return cls(control, lookup, training, prediction, status)
