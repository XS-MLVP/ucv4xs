"""bpuverify.sc.driver.encoding components."""

from __future__ import annotations
from typing import Any
from bpuverify.common.model.folded_history import folded_history_values, PHR_FOLD_LAYOUT
from typing import Sequence
from bpuverify.sc.transaction.types import ScBaseBranch
from bpuverify.sc.transaction.types import ScBranchFeedback
from bpuverify.sc.transaction.types import ScLookup


def _mbtb_result(position: int, valid: int, branch_type: int) -> tuple[Any, ...]:
    return tuple(
        {
            "valid": int(index == 0 and valid),
            "bits": {
                "attribute": {
                    "branchType": branch_type if index == 0 else 0,
                    "rasAction": 0,
                },
                "cfiPosition": position + index,
                "taken": 0,
                "target_addr": 0,
            },
        }
        for index in range(4)
    )


def _provider_counters(value: int, valid: int) -> tuple[Any, ...]:
    return tuple(
        {"valid": int(index == 0 and valid), "bits_value": value}
        for index in range(4)
    )


def _sc_s2_context(request: ScLookup, capacity: int) -> dict[str, Any]:
    entries = (
        (ScBaseBranch(
            request.position, request.tage_counter,
            request.provider_valid, request.mbtb_valid, request.branch_type,
        ),)
        if request.branches is None else request.branches
    )
    if not entries or len(entries) > capacity or all(branch is None for branch in entries):
        raise ValueError(f"SC needs 1..{capacity} MainBTB slots, including a branch")
    positions = [branch.position for branch in entries if branch is not None]
    if len(positions) != len(set(positions)):
        raise ValueError("valid SC branch positions must be distinct")
    if any(branch is not None and branch.position < 0 for branch in entries):
        raise ValueError("SC branch positions must be nonnegative")
    occupied = set(positions)
    fallback = min(positions) + 1
    padded: list[ScBaseBranch | None] = list(entries)
    padded.extend([None] * (capacity - len(padded)))
    mbtb_result = []
    provider_counters = []
    for branch in padded:
        if branch is None:
            while fallback in occupied:
                fallback += 1
            position = fallback
            occupied.add(position)
        else:
            position = branch.position
        mbtb_result.append({
            "valid": 0 if branch is None else branch.mbtb_valid,
            "bits": {
                "attribute": {
                    "branchType": 0 if branch is None else branch.branch_type,
                    "rasAction": 0,
                },
                "cfiPosition": position,
                "taken": 0,
                "target_addr": 0,
            },
        })
        provider_counters.append({
            "valid": 0 if branch is None else branch.provider_valid,
            "bits_value": 0 if branch is None else branch.tage_counter,
        })
    return {"mbtb_result": tuple(mbtb_result), "provider_counters": tuple(provider_counters)}


def _mbtb_meta_branches(
    branches: Sequence[ScBranchFeedback | None],
    *,
    banks: int,
    entries_per_bank: int,
) -> tuple[Any, ...]:
    by_slot = {
        branch.prediction_slot: branch
        for branch in branches if branch is not None
    }
    matrix = []
    for bank in range(banks):
        row = []
        for entry in range(entries_per_bank):
            branch = by_slot.get(bank * entries_per_bank + entry)
            row.append({
                "rawHit": 0 if branch is None else int(branch.mbtb_hit),
                "position": 0 if branch is None else branch.position,
                "attribute": {
                    "branchType": 0 if branch is None else branch.branch_type,
                    "rasAction": 0,
                },
                "counter_value": 0,
            })
        matrix.append(tuple(row))
    return tuple(matrix)


def _encode_s0(request: ScLookup) -> dict[str, Any]:
    return {
        "fire": 1,
        "start_pc": request.pc,
        **encode_history(request.history),
    }


def encode_history(history):
    return dict(common_hr_valid=int(history.common_valid), global_history=history.global_history,
                backward=history.backward, loop=history.loop,
                path_history=folded_history_values(history.path, len(PHR_FOLD_LAYOUT)))
