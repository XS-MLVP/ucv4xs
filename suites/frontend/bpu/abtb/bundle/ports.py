"""suites.frontend.bpu.abtb.bundle.ports components."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from toffee import Bundle
from suites.frontend.bpu.ports.bindings import ConstantLeaf
from suites.frontend.bpu.ports.bindings import PortBinding
from suites.frontend.bpu.ports.bindings import PulseBinding
from suites.frontend.bpu.ports.bindings import bind_bundle
from suites.frontend.bpu.ports.bindings import bind_leaf
from suites.frontend.bpu.ports.bindings import bind_pulse
from suites.frontend.bpu.ports.bindings import bind_sequence


@dataclass(frozen=True, slots=True)
class AbtbPorts:
    control: PortBinding
    lookup: PortBinding
    training: PulseBinding
    prediction: PortBinding
    status: PortBinding

    @classmethod
    def bind(cls, dut: Any) -> "AbtbPorts":
        # Whole-chip elaboration keeps only the PHR history element consumed
        # by AheadBTB (index 2) and drops the unused s3 stage control, so the
        # io aggregate cannot be bound as one contiguous sequence.
        def leaf(*parts: str):
            return bind_leaf(dut, ("io",) + parts, name="abtb.io." + ".".join(parts))

        def aggregate(*parts: str):
            return bind_bundle(
                dut, ("io",) + parts, name="abtb.io." + ".".join(parts)
            ).bits

        stage = aggregate("stageCtrl")
        control = PortBinding(dut.clock, Bundle(enable=leaf("enable")), "abtb.control")
        lookup = PortBinding(
            dut.clock,
            Bundle(
                s0_fire=stage.s0_fire,
                s1_fire=stage.s1_fire,
                s2_fire=stage.s2_fire,
                start_pc=leaf("startPc_addr"),
                new_start_pc=leaf("newStartPc_addr"),
                # AbtbHashFhInfo reuses folded PHR entry 2; RTL hashes its low 4 bits.
                path_hash=leaf("normalPathHist_hist", "2", "foldedHist"),
                s2_override=leaf("bpuS2Override"),
                s3_override=leaf("bpuS3Override"),
                override_start_pc=leaf("overrideStartPc_addr"),
                redirect=leaf("redirect"),
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
                entries=bind_sequence(
                    dut, ("io", "result_entries"), name="abtb.io.result_entries"
                ),
                meta=aggregate("meta"),
                micro_tage=aggregate("toMicroTage"),
            ),
            "abtb.prediction",
        )
        status = PortBinding(
            dut.clock,
            Bundle(
                reset_done=leaf("sramResetDone"),
                # AheadBtb.scala declares `io.trainReady := true.B`; the
                # constant output was folded away by whole-chip DCE.
                train_ready=ConstantLeaf(1),
            ),
            "abtb.status",
        )
        return cls(control, lookup, training, prediction, status)
