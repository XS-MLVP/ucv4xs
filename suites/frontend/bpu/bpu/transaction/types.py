"""suites.frontend.bpu.bpu.transaction.types components."""

from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass
from dataclasses import field
from enum import IntEnum
from typing import Any


@dataclass(frozen=True, slots=True)
class BpuPrediction:
    start_pc: int
    target: int
    taken: int
    position: int
    s2_override: int
    s3_override: int


class BpuStage1Source(IntEnum):
    UBTB = 0
    ABTB = 1
    UBTB_UTAGE = 2
    ABTB_UTAGE = 3
    FALLTHROUGH = 4


@dataclass(frozen=True, slots=True)
class BpuPerf:
    """S3 metadata echo of the accepted S1 prediction and its source."""

    start_pc: int
    s1_target: int
    s1_taken: int
    s1_position: int
    s1_source: BpuStage1Source


@dataclass(frozen=True, slots=True)
class BpuMeta:
    resolve: Any
    redirect: Any
    perf: BpuPerf


@dataclass(frozen=True, slots=True)
class BpuBackpressure:
    prediction_valid: tuple[int, int]
    prediction: tuple[BpuPrediction, BpuPrediction]


@dataclass(frozen=True, slots=True)
class BpuPredictionSample:
    """A prediction observed while FTQ backpressure prevents acceptance."""

    valid: int
    prediction: BpuPrediction


@dataclass(frozen=True, slots=True)
class BpuStalledRedirect:
    stalled_valid: int
    stalled_prediction: BpuPrediction
    redirected_valid: int
    redirected_prediction: BpuPrediction
    first_accepted_tick: int
    first_accepted_prediction: BpuPrediction


@dataclass(frozen=True, slots=True)
class BpuConcurrentActivity:
    training_tick: int
    prediction_ticks: tuple[int, ...]
    predictions: tuple[BpuPrediction, ...]


@dataclass(frozen=True, slots=True)
class BpuBurstActivity:
    training_ticks: tuple[int, ...]
    prediction_ticks: tuple[int, ...]
    predictions: tuple[BpuPrediction, ...]


@dataclass(frozen=True, slots=True)
class BpuTransaction:
    prediction_tick: int
    meta_tick: int
    prediction: BpuPrediction
    meta: BpuMeta


@dataclass(frozen=True, slots=True)
class BpuTraining:
    pc: int
    position: int
    target: int
    resolve_meta: Any
    branch_type: int = 2
    ras_action: int = 0
    taken: int = 1
    mispredict: int = 1


@dataclass(frozen=True, slots=True)
class BpuBranchFeedback:
    position: int
    target: int
    branch_type: int
    taken: int = 1
    mispredict: int = 0
    ras_action: int = 0


@dataclass(frozen=True, slots=True)
class BpuBatchTraining:
    """One FTQ feedback beat; ``None`` preserves an invalid branch slot."""

    pc: int
    resolve_meta: Any
    branches: tuple[BpuBranchFeedback | None, ...]


@dataclass(frozen=True, slots=True)
class BpuRedirect:
    """FTQ recovery; ``pc`` is the target, not necessarily the branch PC.

    The two-positional-argument form keeps its original taken-jump behavior.
    Explicit branch fields are keyword-only to avoid ambiguous transactions.
    """

    pc: int
    meta: Any
    cfi_pc: int | None = field(default=None, kw_only=True)
    taken: int = field(default=1, kw_only=True)
    branch_type: int = field(default=2, kw_only=True)
    ras_action: int = field(default=0, kw_only=True)

    def payload(self) -> dict[str, Any]:
        for name, value, width in (
            ("pc", self.pc, 50),
            ("taken", self.taken, 1),
            ("branch_type", self.branch_type, 2),
            ("ras_action", self.ras_action, 2),
        ):
            if type(value) is not int or not 0 <= value < 1 << width:
                raise ValueError(f"{name} must be an unsigned {width}-bit integer")
        cfi_pc = self.cfi_pc
        if cfi_pc is None:
            # Preserve the legacy port's 49-bit truncation for signGuard PCs.
            cfi_pc = self.pc & ((1 << 49) - 1)
        elif type(cfi_pc) is not int or not 0 <= cfi_pc < 1 << 49:
            raise ValueError("cfi_pc must be an unsigned 49-bit integer")
        return dict(meta=deepcopy(self.meta), cfi_pc=cfi_pc, target=self.pc,
                    taken=self.taken, branch_type=self.branch_type, ras_action=self.ras_action)
