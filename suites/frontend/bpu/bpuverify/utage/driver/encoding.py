"""bpuverify.utage.driver.encoding components."""

from __future__ import annotations
from typing import Any
from bpuverify.utage.transaction.types import UtageBaseBranch
from bpuverify.utage.transaction.types import UtageTraining


def _ahead_btb(
    position: int,
    taken: int,
    branches: tuple[UtageBaseBranch | None, ...] | None = None,
    *,
    capacity: int,
) -> dict[str, Any]:
    entries = (UtageBaseBranch(position, taken),) if branches is None else branches
    if not entries or len(entries) > capacity or all(branch is None for branch in entries):
        raise ValueError(f"MicroTAGE needs 1..{capacity} AheadBTB slots, including a valid branch")
    positions = [branch.position for branch in entries if branch is not None]
    if len(positions) != len(set(positions)):
        raise ValueError("valid AheadBTB branches must have distinct positions")
    if any(branch is not None and branch.position < 0 for branch in entries):
        raise ValueError("AheadBTB positions must be nonnegative")
    occupied = set(positions)
    fallback = min(positions) + 1
    padded: list[UtageBaseBranch | None] = list(entries)
    padded.extend([None] * (capacity - len(padded)))
    fast_positions = []
    for branch in padded:
        if branch is None:
            while fallback in occupied:
                fallback += 1
            fast_positions.append(fallback)
            occupied.add(fallback)
        else:
            fast_positions.append(branch.position)
    return {
        "fastPositions": tuple(fast_positions),
        "result": tuple(
            {
                "valid": int(branch is not None),
                "bits": {
                    "attribute": {"branchType": 0 if branch is None else branch.branch_type, "rasAction": 0},
                    "cfiPosition": fast_positions[index],
                    "isStrongBias": 0 if branch is None else branch.strong_bias,
                    "taken": 0 if branch is None else branch.taken,
                },
            }
            for index, branch in enumerate(padded)
        ),
    }


def encode_training(transaction: UtageTraining) -> dict[str, Any]:
    return {
        "start_pc": transaction.pc,
        "meta": transaction.meta,
        "branch": {
            "taken": transaction.actual_taken,
            "position": transaction.position,
            "branch_type": transaction.branch_type,
            "ras_action": transaction.ras_action,
            "mispredict": transaction.mispredict,
        },
    }
