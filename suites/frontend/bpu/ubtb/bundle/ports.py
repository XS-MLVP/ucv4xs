"""suites.frontend.bpu.ubtb.bundle.ports components."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from toffee import Bundle
from suites.frontend.bpu.ports.bindings import PortBinding
from suites.frontend.bpu.ports.bindings import PulseBinding
from suites.frontend.bpu.ports.bindings import bind_bundle
from suites.frontend.bpu.ports.bindings import bind_pulse
from suites.frontend.bpu.ports.bindings import ConstantLeaf


@dataclass(frozen=True, slots=True)
class UbtbPorts:
    control: PortBinding
    lookup: PortBinding
    fast_train: PulseBinding
    training: PulseBinding
    prediction: PortBinding
    status: PortBinding

    @classmethod
    def bind(cls, dut: Any) -> "UbtbPorts":
        """Bind protocol views from picker's generated hierarchy metadata."""

        io = bind_bundle(dut, ("io",), name="ubtb.io").bits
        control = PortBinding(dut.clock, Bundle(enable=io.enable), "ubtb.control")
        lookup = PortBinding(
            dut.clock,
            Bundle(
                s0_fire=io.stageCtrl.s0_fire,
                s1_fire=io.stageCtrl.s1_fire,
                start_pc=io.startPc_addr,
            ),
            "ubtb.lookup",
        )

        full_train = bind_pulse(dut, ("io", "fastTrain"), name="ubtb.fast_train")
        train_bits = full_train.bits.view_as(
            {
                "start_pc": "startPc_addr",
                # HasFastTrainIO carries BranchInfo without a mispredict leaf:
                # an S3 fast train is by construction the correction of a bad
                # prediction. Only backend resolve feedback has that bit.
                "branch": {
                    "target": "branch.target_addr",
                    "taken": "branch.taken",
                    "position": "branch.cfiPosition",
                    "branch_type": "branch.attribute.branchType",
                    "ras_action": "branch.attribute.rasAction",
                },
            },
            path="ubtb.fast_train.bits",
        )
        fast_train = PulseBinding(
            full_train.clock,
            full_train.valid,
            train_bits,
            full_train.name,
        )
        resolve = bind_bundle(dut, ("io", "train"), name="ubtb.resolve").bits
        training = PulseBinding(
            dut.clock,
            io.stageCtrl.t0_fire,
            Bundle(
                start_pc=resolve.startPcVec_dup[0][0].addr,
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
                    for branch in resolve.branches
                ),
            ),
            "ubtb.training",
        )
        # Whole-chip elaboration dropped MicroBTB's unused prediction.valid
        # output and the resulting io.prediction aggregate node. The
        # always-taken cache's validity is exactly "enabled and a taken
        # prediction is available", so rebuild the public payload from its
        # leaves and derive valid instead of inventing an internal signal.
        prediction_bits = bind_bundle(
            dut, ("io", "prediction_bits"), name="ubtb.prediction.bits"
        ).bits
        prediction = PortBinding(
            dut.clock,
            Bundle(valid=prediction_bits.taken, enabled=io.enable, bits=prediction_bits),
            "ubtb.prediction",
        )
        # MicroBtb.scala declares `io.sramResetDone := true.B` and
        # `io.trainReady := true.B`; whole-chip DCE removed both constant
        # outputs. Bind the declared constants, not a fabricated observation.
        status = PortBinding(
            dut.clock,
            Bundle(reset_done=ConstantLeaf(1), train_ready=ConstantLeaf(1)),
            "ubtb.status",
        )
        return cls(control, lookup, fast_train, training, prediction, status)
