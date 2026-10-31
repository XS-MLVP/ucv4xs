"""Reusable MainBTB transactions and domain assertions."""

from __future__ import annotations

from suites.frontend.bpu.models.configuration import ALIGN_HALFWORDS, MAIN_WAYS
from suites.frontend.bpu.mbtb.transaction.types import MbtbTraining
from suites.frontend.bpu.mbtb.case.definitions import BranchVector


def _align_segment(vector: BranchVector):
    align = (((vector.pc >> 4) & 1) ^ ((vector.position // ALIGN_HALFWORDS) % 2))
    start = align * (MAIN_WAYS + 1)
    return align, start, start + MAIN_WAYS + 1, vector.position % ALIGN_HALFWORDS


def matching_entry(prediction, vector: BranchVector):
    _, start, stop, _ = _align_segment(vector)
    matches = [
        entry
        for entry in prediction.entries[start:stop]
        if entry.valid
        and entry.position == vector.position
        and entry.branch_type == vector.branch_type
    ]
    assert len(matches) == 1, (
        f"expected one MainBTB entry for {vector!r}, actual={prediction!r}"
    )
    return matches[0]


def matching_way(prediction, vector: BranchVector) -> int:
    """Locate a visible entry in the flattened MainBTB way vector."""

    matching_entry(prediction, vector)
    _, start, stop, _ = _align_segment(vector)
    return next(
        index
        for index, entry in enumerate(prediction.entries[start:stop], start=start)
        if entry.valid
        and entry.position == vector.position
        and entry.branch_type == vector.branch_type
    )


def assert_vector_hit(prediction, vector: BranchVector) -> None:
    entry = matching_entry(prediction, vector)
    assert entry.target == vector.target


def assert_miss(prediction) -> None:
    assert not any(entry.valid for entry in prediction.entries), prediction


def assert_filtered_raw_hit(prediction, position: int) -> None:
    """A stored tag matched, but the current fetch window must hide it."""

    assert any(
        item["rawHit"] and item["position"] == position
        for bank in prediction.meta_entries
        for item in bank
    ), f"expected raw hit at position {position}, actual={prediction!r}"
    assert_miss(prediction)


def require_valid(prediction) -> None:
    assert any(entry.valid for entry in prediction.entries), prediction


def matching_counter(prediction, vector: BranchVector) -> int:
    align, _, _, _ = _align_segment(vector)
    matches = [
        item["counter_value"]
        for item in prediction.meta_entries[align]
        if item["rawHit"] and item["position"] == vector.position
    ]
    assert len(matches) == 1, (
        f"expected one MainBTB counter for {vector!r}, "
        f"meta={prediction.meta_entries!r}"
    )
    return matches[0]


def assert_resident_pair(
    prediction, active, neighbor, ways, active_counter, *, neighbor_counter=2
) -> None:
    """Check two same-bank entries retain type, payload, way, and counter."""

    assert sum(entry.valid for entry in prediction.entries) == 2
    assert_vector_hit(prediction, active)
    assert_vector_hit(prediction, neighbor)
    assert matching_way(prediction, active) == ways[0]
    assert matching_way(prediction, neighbor) == ways[1]
    assert matching_counter(prediction, active) == active_counter
    assert matching_counter(prediction, neighbor) == neighbor_counter
    assert matching_entry(prediction, active).taken == int(active_counter >= 2)
    assert matching_entry(prediction, neighbor).taken == int(neighbor_counter >= 2)


async def train(
    agent, vector: BranchVector, meta_entries, *, taken: int = 1, mispredict: int = 1
) -> None:
    await agent.train(
        MbtbTraining(
            pc=vector.pc,
            target=vector.target,
            taken=taken,
            position=vector.position,
            branch_type=vector.branch_type,
            ras_action=vector.ras_action,
            meta_entries=meta_entries,
            mispredict=mispredict,
        )
    )
