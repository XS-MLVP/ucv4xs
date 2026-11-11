"""suites.frontend.bpu.testbenches.bpu.env.driver.encoding components."""

from __future__ import annotations
from suites.frontend.bpu.testbenches.bpu.model.configuration import *
from typing import Any
from suites.frontend.bpu.testbenches.bpu.transactions.types import BpuBatchTraining
from suites.frontend.bpu.testbenches.bpu.transactions.types import BpuBranchFeedback
from suites.frontend.bpu.testbenches.bpu.transactions.types import BpuTraining
from suites.frontend.bpu.testbenches.bpu.transactions.types import validate_phr_metadata


def _single_training(transaction: BpuTraining) -> BpuBatchTraining:
    return BpuBatchTraining(
        transaction.pc,
        transaction.resolve_meta,
        (BpuBranchFeedback(
            transaction.position,
            transaction.target,
            transaction.branch_type,
            taken=transaction.taken,
            mispredict=transaction.mispredict,
            ras_action=transaction.ras_action,
        ),),
    )


def _encode_training(bits: Any, transaction: BpuBatchTraining) -> None:
    validate_phr_metadata(transaction.resolve_meta)
    if type(transaction.pc) is not int or not 0 <= transaction.pc < 1 << 49:
        raise ValueError('BPU training PC must be an unsigned 49-bit halfword address')
    capacity = len(bits.branches)
    if not 1 <= len(transaction.branches) <= capacity:
        raise ValueError(f"BPU feedback requires 1 to {capacity} branch slots")
    active = [branch for branch in transaction.branches if branch is not None]
    if not active:
        raise ValueError("BPU feedback requires at least one valid branch")
    if sum(bool(branch.mispredict) for branch in active) > 1:
        raise ValueError("BPU feedback permits at most one mispredicted branch")
    padded = transaction.branches + (None,) * (capacity - len(transaction.branches))
    bits.drive(
        {
            "meta": transaction.resolve_meta,
            # Whole-chip DefaultConfig retains only the head in copies0/1,
            # but BOTH logical starts in MainBTB's copy2. Do not truncate the
            # genuine successor or drive missing copies of it.
            "start_pcs": (({"addr": transaction.pc},), ({"addr": transaction.pc},),
                ({"addr": transaction.pc},
                 {"addr": (transaction.pc + ALIGN_HALFWORDS) & ~(ALIGN_HALFWORDS - 1)})),
            "branches": tuple({
                "valid": int(branch is not None),
                "bits": {
                    "target_addr": 0 if branch is None else branch.target,
                    "taken": 0 if branch is None else branch.taken,
                    "cfiPosition": 0 if branch is None else branch.position,
                    "attribute": {
                        "branchType": 0 if branch is None else branch.branch_type,
                        "rasAction": 0 if branch is None else branch.ras_action,
                    },
                    "mispredict": 0 if branch is None else branch.mispredict,
                },
            } for branch in padded),
        }
    )
