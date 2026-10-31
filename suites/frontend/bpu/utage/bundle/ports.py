"""suites.frontend.bpu.utage.bundle.ports components."""

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


def _history(dut: Any, path: tuple[str, ...]):
    """Bind a sparse folded-history port into the full configured tuple.

    Whole-chip DCE keeps only the fold indices actually consumed by MicroTage
    (normal index folds for the two tables, tag folds for S1/override/train).
    The semantic reference reconstructs the complete 33-fold context from
    these sparse rows; missing indices are not part of this build's input.
    """

    present = tuple(sorted(int(child) for child in tree_children(dut, path)))
    if len(set(present)) != len(present):
        raise ValueError(f"{'.'.join(path)} has duplicate history indices")
    values = []
    for index in present:
        width = PHR_FOLD_LAYOUT[index][1]
        signal = bind_leaf(
            dut, path + (str(index), "foldedHist"),
            name=f"{'.'.join(path)}[{index}].foldedHist")
        if signal_width(signal) != width:
            raise ValueError(
                f"{'.'.join(path)}[{index}] width {signal_width(signal)} "
                f"!= layout {width}")
        values.append(Bundle(foldedHist=signal))
    return tuple(values), present


@dataclass(frozen=True, slots=True)
class UtagePorts:
    control: PortBinding
    lookup: PortBinding
    training: PulseBinding
    prediction: PortBinding
    status: PortBinding
    normal_history_indices: tuple[int, ...] = ()
    s1_history_indices: tuple[int, ...] = ()
    override_history_indices: tuple[int, ...] = ()
    training_history_indices: tuple[int, ...] = ()
    training_observation: PulseBinding | None = None

    @classmethod
    def bind(cls, dut: Any) -> "UtagePorts":
        def leaf(*parts: str):
            return bind_leaf(dut, ("io",) + parts,
                             name="utage.io." + ".".join(parts))

        def aggregate(*parts: str):
            return bind_bundle(dut, ("io",) + parts,
                               name="utage.io." + ".".join(parts)).bits

        def meta_bundle(prefix: str, path: tuple[str, ...], *, dense=False):
            indices = tuple(sorted(
                int(child) for child in tree_children(dut, path + ("foldedPathHistForTrain_hist",))))
            if dense:
                rows = []
                for index in range(len(PHR_FOLD_LAYOUT)):
                    width = PHR_FOLD_LAYOUT[index][1]
                    if index in indices:
                        rows.append(Bundle(foldedHist=bind_leaf(
                            dut, path + ("foldedPathHistForTrain_hist", str(index), "foldedHist"),
                            name=f"{prefix}.foldedPathHistForTrain_hist[{index}]")))
                    else:
                        rows.append(Bundle(foldedHist=ConstantLeaf(0, width)))
            else:
                rows = [Bundle(foldedHist=bind_leaf(
                    dut, path + ("foldedPathHistForTrain_hist", str(index), "foldedHist"),
                    name=f"{prefix}.foldedPathHistForTrain_hist[{index}]"))
                    for index in indices]
            return Bundle(
                abtbResult=bind_sequence(
                    dut, path + ("abtbResult",),
                    name=f"{prefix}.abtbResult"),
                foldedPathHistForTrain_hist=tuple(rows),
                readIndex=tuple(
                    bind_leaf(dut, path + ("readIndex", str(index)),
                              name=f"{prefix}.readIndex[{index}]")
                    for index in range(len(tree_children(dut, path + ("readIndex",))))),
            ), indices

        normal, normal_indices = _history(dut, ("io", "normalPathHist_hist"))
        s1, s1_indices = _history(dut, ("io", "s1PathHist_hist"))
        override, override_indices = _history(dut, ("io", "overridePathHist_hist"))
        control = PortBinding(dut.clock, Bundle(enable=leaf("enable")), "utage.control")
        lookup = PortBinding(
            dut.clock,
            Bundle(
                s0_fire=leaf("stageCtrl", "s0_fire"),
                s2_fire=leaf("stageCtrl", "s2_fire"),
                s2_override=leaf("bpuS2Override"),
                s3_override=leaf("bpuS3Override"),
                start_pc=leaf("startPc_addr"),
                new_start_pc=leaf("newStartPc_addr"),
                override_start_pc=leaf("overrideStartPc_addr"),
                redirect=leaf("redirect"),
                normal_history=normal,
                s1_history=s1,
                override_history=override,
                ahead_btb=aggregate("fromAheadBtb"),
            ),
            "utage.lookup",
        )
        # The fastTrain aggregate contains the same sparse training-history
        # subtree as meta_bits, so it cannot be bound as one contiguous tree.
        train_meta, training_indices = meta_bundle(
            "utage.fast_train.bits.utageMeta",
            ("io", "fastTrain", "bits", "utageMeta"))
        branch = aggregate("fastTrain", "bits", "branch")
        training = PulseBinding(
            dut.clock,
            leaf("fastTrain", "valid"),
            Bundle(
                start_pc=leaf("fastTrain", "bits", "startPc_addr"),
                meta=train_meta,
                branch=Bundle(
                    taken=branch.taken,
                    position=branch.cfiPosition,
                    branch_type=branch.attribute_branchType,
                ),
            ),
            "utage.fast_train",
        )
        prediction_meta, prediction_indices = meta_bundle(
            "utage.io.meta_bits", ("io", "meta_bits"))
        observation_meta, _ = meta_bundle(
            "utage.observation_meta", ("io", "fastTrain", "bits", "utageMeta"),
            dense=True)
        observation_branch = aggregate("fastTrain", "bits", "branch")
        training_observation = PulseBinding(
            dut.clock,
            leaf("fastTrain", "valid"),
            Bundle(
                start_pc=leaf("fastTrain", "bits", "startPc_addr"),
                meta=observation_meta,
                branch=Bundle(
                    taken=observation_branch.taken,
                    position=observation_branch.cfiPosition,
                    branch_type=observation_branch.attribute_branchType,
                ),
            ),
            "utage.training_observation",
        )
        if prediction_indices != training_indices:
            raise ValueError("prediction/training metadata history layout differs")
        prediction_bits = aggregate("prediction")
        prediction = PortBinding(
            dut.clock,
            Bundle(
                hit=prediction_bits.hitVec[0],
                taken=prediction_bits.takenVec[0],
                hits=prediction_bits.hitVec,
                takens=prediction_bits.takenVec,
                meta=prediction_meta,
            ),
            "utage.prediction",
        )
        # MicroTage.scala declares `io.trainReady := true.B`; the constant
        # output was folded away by whole-chip DCE.
        status = PortBinding(
            dut.clock,
            Bundle(reset_done=leaf("sramResetDone"), train_ready=ConstantLeaf(1)),
            "utage.status",
        )
        ports = cls(control, lookup, training, prediction, status,
                    normal_indices, s1_indices, override_indices,
                    training_indices)
        object.__setattr__(ports, 'training_observation', training_observation)
        return ports
