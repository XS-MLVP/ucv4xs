"""bpuverify.ittage.bundle.ports components."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from toffee import Bundle
from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.common.bundle.bindings import PulseBinding
from bpuverify.common.bundle.bindings import bind_bundle


@dataclass(frozen=True, slots=True)
class IttagePorts:
    control: PortBinding
    lookup: PortBinding
    training: PulseBinding
    prediction: PortBinding
    status: PortBinding

    @classmethod
    def bind(cls, dut: Any) -> "IttagePorts":
        io = bound = bind_bundle(dut, ("io",), name="ittage.io").bits
        control = PortBinding(dut.clock, Bundle(enable=io.enable), "ittage.control")
        lookup = PortBinding(
            dut.clock,
            Bundle(
                s0_fire=io.stageCtrl.s0_fire,
                s1_fire=io.stageCtrl.s1_fire,
                s2_fire=io.stageCtrl.s2_fire,
                s3_fire=io.stageCtrl.s3_fire,
                start_pc=io.startPc_addr,
                folded_history=bound.s1_foldedPhr_hist,
            ),
            "ittage.lookup",
        )
        training = PulseBinding(
            dut.clock,
            io.stageCtrl.t0_fire,
            Bundle(
                start_pc=io.train.startPcVec_dup[0][0].addr,
                folded_history=bound.trainFoldedPhr_hist,
                meta=bound.train.meta.ittage,
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
                    for branch in bound.train.branches
                ),
            ),
            "ittage.training",
        )
        prediction = PortBinding(
            dut.clock,
            Bundle(
                hit=bound.prediction.hit,
                target=bound.prediction.target_addr,
                meta=bound.meta,
            ),
            "ittage.prediction",
        )
        status = PortBinding(
            dut.clock,
            Bundle(reset_done=io.sramResetDone, train_ready=io.trainReady),
            "ittage.status",
        )
        return cls(control, lookup, training, prediction, status)
