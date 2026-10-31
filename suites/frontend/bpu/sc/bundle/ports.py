"""suites.frontend.bpu.sc.bundle.ports components."""

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
class ScPorts:
    control: PortBinding
    lookup: PortBinding
    training: PulseBinding
    prediction: PortBinding
    status: PortBinding
    history_indices: tuple[int, ...] = ()

    @classmethod
    def bind(cls, dut: Any) -> "ScPorts":
        def leaf(*parts: str):
            return bind_leaf(dut, ("io",) + parts,
                             name="sc.io." + ".".join(parts))

        def aggregate(*parts: str):
            return bind_bundle(dut, ("io",) + parts,
                               name="sc.io." + ".".join(parts)).bits

        def sequence(*parts: str):
            return bind_sequence(dut, ("io",) + parts,
                                 name="sc.io." + ".".join(parts))

        def nested_sequence(*parts: str):
            path = ("io",) + parts
            count = len(tree_children(dut, path))
            return tuple(bind_sequence(dut, path + (str(index),),
                                       name="sc.io." + ".".join(parts) + f"[{index}]")
                         for index in range(count))

        path_history, history_indices = _history(
            dut, ("io", "foldedPathHist_hist"), "sc.io.foldedPathHist_hist")
        train_history, train_indices = _history(
            dut, ("io", "trainFoldedPathHist_hist"), "sc.io.trainFoldedPathHist_hist")
        if history_indices != train_indices:
            raise ValueError("SC lookup/training history layouts differ")
        control = PortBinding(dut.clock, Bundle(enable=leaf("enable")),
                              "sc.control")
        lookup = PortBinding(
            dut.clock,
            Bundle(
                s0_fire=leaf("stageCtrl", "s0_fire"),
                s1_fire=leaf("stageCtrl", "s1_fire"),
                s2_fire=leaf("stageCtrl", "s2_fire"),
                start_pc=leaf("startPc_addr"),
                common_hr_valid=leaf("commonHR", "valid"),
                global_history=leaf("commonHR", "ghr"),
                backward=leaf("commonHR", "bw"),
                loop=leaf("imli"),
                path_history=path_history,
                mbtb_result=sequence("mbtbResult"),
                provider_counters=sequence("providerTakenCtrs"),
            ),
            "sc.lookup",
        )
        training = PulseBinding(
            dut.clock,
            leaf("stageCtrl", "t0_fire"),
            Bundle(
                start_pc=leaf("train", "startPcVec_dup", "0", "0", "addr"),
                common_hr_valid=leaf("train", "meta", "commonHR", "valid"),
                global_history=leaf("train", "meta", "commonHR", "ghr"),
                backward=leaf("train", "meta", "commonHR", "bw"),
                loop=leaf("train", "meta", "commonHR", "imli"),
                path_history=train_history,
                mbtb_meta=nested_sequence("train", "meta", "mbtb_entries"),
                sc_meta=aggregate("train", "meta", "sc"),
                branches=tuple(
                    Bundle(
                        valid=branch.valid,
                        taken=branch.bits.taken,
                        position=branch.bits.cfiPosition,
                        branch_type=branch.bits.attribute_branchType,
                    )
                    for branch in sequence("train", "branches")
                ),
            ),
            "sc.training",
        )
        prediction = PortBinding(
            dut.clock,
            Bundle(
                taken=leaf("scTakenMask", "0"),
                used=leaf("scUsed", "0"),
                takens=tuple(leaf("scTakenMask", str(index)) for index in range(10)),
                useds=tuple(leaf("scUsed", str(index)) for index in range(10)),
                meta=aggregate("meta"),
            ),
            "sc.prediction",
        )
        status = PortBinding(
            dut.clock,
            Bundle(reset_done=leaf("sramResetDone"), train_ready=leaf("trainReady")),
            "sc.status",
        )
        return cls(control, lookup, training, prediction, status,
                   history_indices)
