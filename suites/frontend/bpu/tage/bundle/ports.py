"""suites.frontend.bpu.tage.bundle.ports components."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from toffee import Bundle
from toffee.signals import signal_width
from suites.frontend.bpu.ports.bindings import PortBinding
from suites.frontend.bpu.ports.bindings import PulseBinding
from suites.frontend.bpu.ports.bindings import bind_bundle
from suites.frontend.bpu.ports.bindings import bind_leaf
from suites.frontend.bpu.ports.bindings import bind_sequence
from suites.frontend.bpu.ports.bindings import tree_children
from suites.frontend.bpu.models.folded_history import PHR_FOLD_LAYOUT


def _history(dut: Any, path: tuple[str, ...], label: str):
    """Bind the fold rows TAGE actually consumes on this build.

    Whole-chip DCE keeps only the 20 folds that participate in TAGE index,
    primary and secondary hashes.  Return both the sparse rows and their
    configured positions so drivers can project a full history value and the
    monitor can reconstruct the configured context with removed folds zeroed.
    """

    present = tuple(sorted(int(child) for child in tree_children(dut, path)))
    if len(set(present)) != len(present):
        raise ValueError(f"{label} has duplicate fold indices")
    rows = []
    for index in present:
        width = PHR_FOLD_LAYOUT[index][1]
        signal = bind_leaf(dut, path + (str(index), "foldedHist"),
                           name=f"{label}[{index}].foldedHist")
        if signal_width(signal) != width:
            raise ValueError(
                f"{label}[{index}] width {signal_width(signal)} != layout {width}")
        rows.append(Bundle(foldedHist=signal))
    return tuple(rows), present


@dataclass(frozen=True, slots=True)
class TagePorts:
    control: PortBinding
    lookup: PortBinding
    training: PulseBinding
    prediction: PortBinding
    status: PortBinding
    lookup_history_indices: tuple[int, ...] = ()
    training_history_indices: tuple[int, ...] = ()

    @classmethod
    def bind(cls, dut: Any) -> "TagePorts":
        def leaf(*parts: str):
            return bind_leaf(dut, ("io",) + parts,
                             name="tage.io." + ".".join(parts))

        def sequence(*parts: str):
            return bind_sequence(dut, ("io",) + parts,
                                 name="tage.io." + ".".join(parts))

        def aggregate(*parts: str):
            return bind_bundle(dut, ("io",) + parts,
                               name="tage.io." + ".".join(parts)).bits

        def nested_sequence(*parts: str):
            path = ("io",) + parts
            count = len(tree_children(dut, path))
            return tuple(
                bind_sequence(dut, path + (str(index),),
                              name="tage.io." + ".".join(parts) + f"[{index}]")
                for index in range(count))

        history, history_indices = _history(
            dut, ("io", "fromPhr", "foldedPathHist_hist"),
            "tage.io.fromPhr.foldedPathHist_hist")
        training_history, training_indices = _history(
            dut, ("io", "fromPhr", "foldedPathHistForTrain_hist"),
            "tage.io.fromPhr.foldedPathHistForTrain_hist")

        control = PortBinding(dut.clock, Bundle(enable=leaf("enable")), "tage.control")
        lookup = PortBinding(
            dut.clock,
            Bundle(
                s0_fire=leaf("stageCtrl", "s0_fire"),
                s1_fire=leaf("stageCtrl", "s1_fire"),
                start_pc=leaf("startPc_addr"),
                history=history,
                main_btb=aggregate("fromMainBtb"),
            ),
            "tage.lookup",
        )
        branches = sequence("train", "branches")
        training = PulseBinding(
            dut.clock,
            leaf("stageCtrl", "t0_fire"),
            Bundle(
                start_pc=leaf("train", "startPcVec_dup", "0", "0", "addr"),
                history=training_history,
                mbtb_meta=nested_sequence("train", "meta", "mbtb_entries"),
                tage_meta=sequence("train", "meta", "tage_entries"),
                branches=tuple(
                    Bundle(
                        valid=branch.valid,
                        taken=branch.bits.taken,
                        position=branch.bits.cfiPosition,
                        branch_type=branch.bits.attribute_branchType,
                        mispredict=branch.bits.mispredict,
                    )
                    for branch in branches
                ),
            ),
            "tage.training",
        )
        taken_vec = sequence("prediction", "takenVec")
        meta_vec = sequence("meta_entries")
        provider_valid = sequence("toSc_providerTakenCtrVec")
        prediction = PortBinding(
            dut.clock,
            Bundle(
                taken=taken_vec[0],
                meta=meta_vec[0],
                provider_counter_valid=provider_valid[0].valid,
                taken_vec=taken_vec,
                meta_vec=meta_vec,
                provider_counter_valid_vec=tuple(
                    entry.valid for entry in provider_valid
                ),
                fast_taken_vec=sequence("prediction", "fastTakenVec"),
                sc_counter_vec=provider_valid,
            ),
            "tage.prediction",
        )
        status = PortBinding(
            dut.clock,
            Bundle(reset_done=leaf("sramResetDone"), train_ready=leaf("trainReady")),
            "tage.status",
        )
        return cls(control, lookup, training, prediction, status,
                   history_indices, training_indices)
