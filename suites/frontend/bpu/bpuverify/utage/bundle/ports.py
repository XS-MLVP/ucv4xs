"""bpuverify.utage.bundle.ports components."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from toffee import Bundle
from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.common.bundle.bindings import PulseBinding
from bpuverify.common.bundle.bindings import bind_bundle
from bpuverify.common.bundle.bindings import bind_pulse


@dataclass(frozen=True, slots=True)
class UtagePorts:
    control: PortBinding
    lookup: PortBinding
    training: PulseBinding
    prediction: PortBinding
    status: PortBinding

    @classmethod
    def bind(cls, dut: Any) -> "UtagePorts":
        io = bound = bind_bundle(dut, ("io",), name="utage.io").bits
        control = PortBinding(dut.clock, Bundle(enable=io.enable), "utage.control")
        lookup = PortBinding(
            dut.clock,
            Bundle(
                s0_fire=io.stageCtrl.s0_fire,
                s2_fire=io.stageCtrl.s2_fire,
                s2_override=io.bpuS2Override,
                s3_override=io.bpuS3Override,
                start_pc=io.startPc_addr,
                new_start_pc=io.newStartPc_addr,
                override_start_pc=io.overrideStartPc_addr,
                redirect=dut.io_redirect,
                normal_history=bound.normalPathHist_hist,
                s1_history=bound.s1PathHist_hist,
                override_history=bound.overridePathHist_hist,
                ahead_btb=bound.fromAheadBtb,
            ),
            "utage.lookup",
        )
        full_train = bind_pulse(dut, ("io", "fastTrain"), name="utage.fast_train")
        training = PulseBinding(
            full_train.clock,
            full_train.valid,
            full_train.bits.view_as(
                {
                    "start_pc": "startPc_addr",
                    "meta": "utageMeta",
                    "branch": {
                        "taken": "branch.taken",
                        "position": "branch.cfiPosition",
                        "branch_type": "branch.attribute.branchType",
                        "ras_action": "branch.attribute.rasAction",
                        "mispredict": "branch.mispredict",
                    },
                },
                path="utage.fast_train.bits",
            ),
            full_train.name,
        )
        prediction = PortBinding(
            dut.clock,
            Bundle(
                hit=bound.prediction.hitVec[0],
                taken=bound.prediction.takenVec[0],
                hits=bound.prediction.hitVec,
                takens=bound.prediction.takenVec,
                meta=bound.meta.bits,
            ),
            "utage.prediction",
        )
        status = PortBinding(
            dut.clock,
            Bundle(reset_done=io.sramResetDone, train_ready=io.trainReady),
            "utage.status",
        )
        return cls(control, lookup, training, prediction, status)
