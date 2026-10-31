"""suites.frontend.bpu.ittage.bundle.ports components."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from toffee import Bundle
from toffee.signals import signal_width
from suites.frontend.bpu.ports.bindings import ConstantLeaf
from suites.frontend.bpu.ports.bindings import PortBinding
from suites.frontend.bpu.ports.bindings import PulseBinding
from suites.frontend.bpu.ports.bindings import bind_bundle
from suites.frontend.bpu.ports.bindings import bind_leaf
from suites.frontend.bpu.ports.bindings import bind_sequence
from suites.frontend.bpu.ports.bindings import tree_children
from suites.frontend.bpu.models.folded_history import PHR_FOLD_LAYOUT


def _history(dut: Any, path: tuple[str, ...], label: str):
    present = tuple(sorted(int(child) for child in tree_children(dut, path)))
    rows = []
    for index in present:
        width = PHR_FOLD_LAYOUT[index][1]
        signal = bind_leaf(dut, path + (str(index), "foldedHist"),
                           name=f"{label}[{index}].foldedHist")
        if signal_width(signal) != width:
            raise ValueError(f"{label}[{index}] width {signal_width(signal)} != {width}")
        rows.append(Bundle(foldedHist=signal))
    return tuple(rows), present


@dataclass(frozen=True, slots=True)
class IttagePorts:
    control: PortBinding
    lookup: PortBinding
    training: PulseBinding
    prediction: PortBinding
    status: PortBinding
    history_indices: tuple[int, ...] = ()

    @classmethod
    def bind(cls, dut: Any) -> "IttagePorts":
        def leaf(*parts: str):
            return bind_leaf(dut, ("io",) + parts,
                             name="ittage.io." + ".".join(parts))

        def aggregate(*parts: str):
            return bind_bundle(dut, ("io",) + parts,
                               name="ittage.io." + ".".join(parts)).bits

        history, history_indices = _history(
            dut, ("io", "s1_foldedPhr_hist"), "ittage.io.s1_foldedPhr_hist")
        train_history, train_indices = _history(
            dut, ("io", "trainFoldedPhr_hist"), "ittage.io.trainFoldedPhr_hist")
        if history_indices != train_indices:
            raise ValueError("ITTAGE lookup/training history layouts differ")
        control = PortBinding(dut.clock, Bundle(enable=leaf("enable")),
                              "ittage.control")
        lookup = PortBinding(
            dut.clock,
            Bundle(
                s0_fire=leaf("stageCtrl", "s0_fire"),
                s1_fire=leaf("stageCtrl", "s1_fire"),
                s2_fire=leaf("stageCtrl", "s2_fire"),
                s3_fire=leaf("stageCtrl", "s3_fire"),
                start_pc=leaf("startPc_addr"),
                folded_history=history,
            ),
            "ittage.lookup",
        )
        branches = bind_sequence(dut, ("io", "train", "branches"),
                                 name="ittage.io.train.branches")
        training = PulseBinding(
            dut.clock,
            leaf("stageCtrl", "t0_fire"),
            Bundle(
                start_pc=leaf("train", "startPcVec_dup", "0", "0", "addr"),
                folded_history=train_history,
                meta=aggregate("train", "meta_ittage"),
                branches=tuple(
                    Bundle(
                        valid=branch.valid,
                        target=branch.bits.target_addr,
                        taken=branch.bits.taken,
                        branch_type=branch.bits.attribute.branchType,
                        ras_action=branch.bits.attribute.rasAction,
                        mispredict=branch.bits.mispredict,
                    )
                    for branch in branches
                ),
            ),
            "ittage.training",
        )
        prediction = PortBinding(
            dut.clock,
            Bundle(
                hit=leaf("prediction", "hit"),
                target=leaf("prediction", "target_addr"),
                meta=aggregate("meta"),
                # Whole-chip DCE removed io.meta.valid; publication is the
                # parent's S3 consume qualification.
                enabled=leaf("enable"),
                consume=leaf("stageCtrl", "s3_fire"),
            ),
            "ittage.prediction",
        )
        # ITTAGE.scala declares ``io.trainReady := true.B``; whole-chip DCE
        # removed the constant pin. Only the SRAM reset-done handshake is a
        # real output of this build.
        status = PortBinding(
            dut.clock,
            Bundle(reset_done=leaf("sramResetDone"), train_ready=ConstantLeaf(1)),
            "ittage.status",
        )
        return cls(control, lookup, training, prediction, status,
                   history_indices)
