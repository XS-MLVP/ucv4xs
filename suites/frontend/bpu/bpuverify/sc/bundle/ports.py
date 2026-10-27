"""bpuverify.sc.bundle.ports components."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from toffee import Bundle
from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.common.bundle.bindings import PulseBinding
from bpuverify.common.bundle.bindings import bind_bundle


@dataclass(frozen=True, slots=True)
class ScPorts:
    control: PortBinding
    lookup: PortBinding
    training: PulseBinding
    prediction: PortBinding
    status: PortBinding

    @classmethod
    def bind(cls, dut: Any) -> "ScPorts":
        io = bound = bind_bundle(dut, ("io",), name="sc.io").bits
        control = PortBinding(dut.clock, Bundle(enable=io.enable), "sc.control")
        lookup = PortBinding(
            dut.clock,
            Bundle(
                s0_fire=io.stageCtrl.s0_fire,
                s1_fire=io.stageCtrl.s1_fire,
                s2_fire=io.stageCtrl.s2_fire,
                start_pc=io.startPc_addr,
                common_hr_valid=io.commonHR.valid,
                global_history=io.commonHR.ghr,
                backward=io.commonHR.bw,
                loop=io.imli,
                path_history=io.foldedPathHist_hist,
                mbtb_result=bound.mbtbResult,
                provider_counters=bound.providerTakenCtrs,
            ),
            "sc.lookup",
        )
        training = PulseBinding(
            dut.clock,
            io.stageCtrl.t0_fire,
            Bundle(
                start_pc=io.train.startPcVec_dup[0][0].addr,
                common_hr_valid=io.train.meta.commonHR.valid,
                global_history=io.train.meta.commonHR.ghr,
                backward=io.train.meta.commonHR.bw,
                loop=io.train.meta.commonHR.imli,
                path_history=io.trainFoldedPathHist_hist,
                mbtb_meta=bound.train.meta.mbtb_entries,
                sc_meta=bound.train.meta.sc,
                branches=tuple(
                    Bundle(
                        valid=branch.valid,
                        taken=branch.bits.taken,
                        position=branch.bits.cfiPosition,
                        branch_type=branch.bits.attribute.branchType,
                    )
                    for branch in io.train.branches
                ),
            ),
            "sc.training",
        )
        prediction = PortBinding(
            dut.clock,
            Bundle(
                taken=bound.scTakenMask[0],
                used=bound.scUsed[0],
                takens=bound.scTakenMask,
                useds=bound.scUsed,
                meta=bound.meta,
            ),
            "sc.prediction",
        )
        status = PortBinding(
            dut.clock,
            Bundle(reset_done=io.sramResetDone, train_ready=io.trainReady),
            "sc.status",
        )
        return cls(control, lookup, training, prediction, status)
