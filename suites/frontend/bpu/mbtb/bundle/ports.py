"""suites.frontend.bpu.mbtb.bundle.ports components."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from toffee import Bundle
from suites.frontend.bpu.ports.bindings import ConstantLeaf
from suites.frontend.bpu.ports.bindings import PortBinding
from suites.frontend.bpu.ports.bindings import PulseBinding
from suites.frontend.bpu.ports.bindings import bind_bundle
from suites.frontend.bpu.ports.bindings import bind_leaf
from suites.frontend.bpu.ports.bindings import bind_sequence
from suites.frontend.bpu.ports.bindings import tree_children


@dataclass(frozen=True, slots=True)
class MbtbPorts:
    control: PortBinding
    lookup: PortBinding
    training: PulseBinding
    prediction: PortBinding
    status: PortBinding

    @classmethod
    def bind(cls, dut: Any) -> "MbtbPorts":
        def leaf(*parts: str):
            return bind_leaf(dut, ("io",) + parts,
                             name="mbtb.io." + ".".join(parts))

        def aggregate(*parts: str):
            return bind_bundle(dut, ("io",) + parts,
                               name="mbtb.io." + ".".join(parts)).bits

        def sequence(*parts: str):
            return bind_sequence(dut, ("io",) + parts,
                                 name="mbtb.io." + ".".join(parts))

        def nested_sequence(*parts: str):
            path = ("io",) + parts
            count = len(tree_children(dut, path))
            return tuple(bind_sequence(dut, path + (str(index),),
                                       name="mbtb.io." + ".".join(parts) + f"[{index}]")
                         for index in range(count))

        control = PortBinding(
            dut.clock, Bundle(enable=leaf("enable")), "mbtb.control"
        )
        # Whole-chip DCE kept only the two victim slots the parent consumes
        # from s3_takenMask; the result vector carries the other positions.
        lookup = PortBinding(
            dut.clock,
            Bundle(
                s0_fire=leaf("stageCtrl", "s0_fire"),
                s1_fire=leaf("stageCtrl", "s1_fire"),
                s2_fire=leaf("stageCtrl", "s2_fire"),
                s3_fire=leaf("stageCtrl", "s3_fire"),
                victim_taken=(leaf("s3_takenMask", "4"), leaf("s3_takenMask", "9")),
                start_pc=leaf("startPc_addr"),
            ),
            "mbtb.lookup",
        )

        training = PulseBinding(
            dut.clock,
            leaf("stageCtrl", "t0_fire"),
            Bundle(
                start_pc0=leaf("train", "startPcVec_dup", "0", "0", "addr"),
                start_pc1=leaf("train", "startPcVec_dup", "0", "1", "addr"),
                meta_entries=nested_sequence("train", "meta_mbtb_entries"),
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
                    for branch in sequence("train", "branches")
                ),
            ),
            "mbtb.training",
        )

        prediction = PortBinding(
            dut.clock,
            Bundle(
                entries=sequence("result"),
                meta_entries=nested_sequence("meta_entries"),
            ),
            "mbtb.prediction",
        )
        # MainBtb.scala declares ``io.trainReady := true.B``; the constant pin
        # was removed by whole-chip DCE.
        status = PortBinding(
            dut.clock,
            Bundle(reset_done=leaf("sramResetDone"), train_ready=ConstantLeaf(1)),
            "mbtb.status",
        )
        return cls(control, lookup, training, prediction, status)
