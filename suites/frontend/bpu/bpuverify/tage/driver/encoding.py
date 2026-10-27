"""bpuverify.tage.driver.encoding components."""

from __future__ import annotations
from typing import Any
from bpuverify.tage.transaction.types import TageBaseBranch
from bpuverify.tage.transaction.types import TageBranchFeedback


def _main_btb(
    position: int,
    taken: int,
    base_conf: int = 0,
    branch_type: int = 1,
    branches: tuple[TageBaseBranch | None, ...] | None = None,
    *,
    capacity: int = 4,
) -> dict[str, Any]:
    entries = (
        (TageBaseBranch(position, taken, base_conf, branch_type),)
        if branches is None else branches
    )
    if not entries or len(entries) > capacity or all(branch is None for branch in entries):
        raise ValueError(f"TAGE needs 1..{capacity} MainBTB slots, including a valid branch")
    positions = [branch.position for branch in entries if branch is not None]
    if len(positions) != len(set(positions)):
        raise ValueError("valid MainBTB branches must have distinct positions")
    if any(branch is not None and branch.position < 0 for branch in entries):
        raise ValueError("MainBTB positions must be nonnegative")
    occupied = set(positions)
    fallback = 0
    padded: list[TageBaseBranch | None] = list(entries)
    padded.extend([None] * (capacity - len(padded)))
    positions_by_slot = []
    for branch in padded:
        if branch is None:
            while fallback in occupied:
                fallback += 1
            positions_by_slot.append(fallback)
            occupied.add(fallback)
        else:
            positions_by_slot.append(branch.position)
    return {
        "baseConf": tuple(0 if branch is None else branch.base_conf for branch in padded),
        "result": tuple(
            {
                "valid": int(branch is not None),
                "bits": {
                    "attribute": {"branchType": 0 if branch is None else branch.branch_type, "rasAction": 0},
                    "cfiPosition": positions_by_slot[index],
                    "taken": 0 if branch is None else branch.taken,
                    "target_addr": 0,
                },
            }
            for index, branch in enumerate(padded)
        ),
        "s1_positions": tuple(positions_by_slot),
    }


def _base_counter(base_taken: int, base_counter_value: int | None = None) -> int:
    counter = (2 if base_taken else 1) if base_counter_value is None else base_counter_value
    if counter not in range(4) or (counter >> 1) != base_taken:
        raise ValueError("MainBTB counter must be 0..3 and match base_taken")
    return counter


def _encode_branch_feedback(branch: TageBranchFeedback | None) -> dict[str, int]:
    if branch is None:
        return {"valid": 0, "taken": 0, "position": 0, "branch_type": 0, "mispredict": 0}
    return {
        "valid": branch.valid,
        "taken": branch.actual_taken,
        "position": branch.position,
        "branch_type": branch.branch_type,
        "mispredict": branch.mispredict,
    }
