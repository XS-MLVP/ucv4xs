"""suites.frontend.bpu.bpu.driver.encoding components."""

from __future__ import annotations
from suites.frontend.bpu.models.configuration import *
from typing import Any
from suites.frontend.bpu.bpu.transaction.types import BpuBatchTraining
from suites.frontend.bpu.bpu.transaction.types import BpuBranchFeedback
from suites.frontend.bpu.bpu.transaction.types import BpuTraining


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
            "start_pcs": tuple(
                # FTQ supplies logical alignment starts; MainBTB rotates them
                # to physical banks. Keep the head's sub-block offset, but
                # advance and align the second 32-byte block (halfword PC).
                ({"addr": transaction.pc}, {"addr": (transaction.pc + ALIGN_HALFWORDS) & ~(ALIGN_HALFWORDS - 1)})
                for _ in range(3)
            ),
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
