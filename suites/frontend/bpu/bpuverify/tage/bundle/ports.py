"""bpuverify.tage.bundle.ports components."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from toffee import Bundle
from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.common.bundle.bindings import PulseBinding
from bpuverify.common.bundle.bindings import bind_bundle


@dataclass(frozen=True, slots=True)
class TagePorts:
    control: PortBinding
    lookup: PortBinding
    training: PulseBinding
    prediction: PortBinding
    status: PortBinding

    @classmethod
    def bind(cls, dut: Any) -> "TagePorts":
        io = bound = bind_bundle(dut, ("io",), name="tage.io").bits
        control = PortBinding(dut.clock, Bundle(enable=io.enable), "tage.control")
        lookup = PortBinding(
            dut.clock,
            Bundle(
                s0_fire=io.stageCtrl.s0_fire,
                s1_fire=io.stageCtrl.s1_fire,
                s2_fire=io.stageCtrl.s2_fire,
                s3_fire=io.stageCtrl.s3_fire,
                start_pc=io.startPc_addr,
                history=io.fromPhr.foldedPathHist_hist,
                main_btb=bound.fromMainBtb,
            ),
            "tage.lookup",
        )
        training = PulseBinding(
            dut.clock,
            io.stageCtrl.t0_fire,
            Bundle(
                start_pc=io.train.startPcVec_dup[0][0].addr,
                history=io.fromPhr.foldedPathHistForTrain_hist,
                mbtb_meta=bound.train.meta.mbtb_entries,
                tage_meta=bound.train.meta.tage_entries,
                branches=tuple(
                    Bundle(
                        valid=branch.valid,
                        taken=branch.bits.taken,
                        position=branch.bits.cfiPosition,
                        branch_type=branch.bits.attribute.branchType,
                        mispredict=branch.bits.mispredict,
                    )
                    for branch in io.train.branches
                ),
            ),
            "tage.training",
        )
        prediction = PortBinding(
            dut.clock,
            Bundle(
                taken=bound.prediction.takenVec[0],
                meta=bound.meta_entries[0],
                provider_counter_valid=bound.toSc_providerTakenCtrVec[0].valid,
                taken_vec=bound.prediction.takenVec,
                meta_vec=bound.meta_entries,
                provider_counter_valid_vec=tuple(
                    entry.valid for entry in bound.toSc_providerTakenCtrVec
                ),
            ),
            "tage.prediction",
        )
        status = PortBinding(
            dut.clock,
            Bundle(reset_done=io.sramResetDone, train_ready=io.trainReady),
            "tage.status",
        )
        return cls(control, lookup, training, prediction, status)
