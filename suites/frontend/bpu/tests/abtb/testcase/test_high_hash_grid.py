"""A high physical set quartet isolates all bank × folded-hash contexts."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.abtb.coverage.catalog import abtb_high_hash_grid_coverage_model
from suites.frontend.bpu.abtb.coverage.catalog import write_abtb_high_hash_grid_coverage
from suites.frontend.bpu.abtb.checker.assertions import age_conditional_to_not_taken
from suites.frontend.bpu.abtb.checker.assertions import assert_conditional_state
from suites.frontend.bpu.abtb.checker.assertions import assert_miss
from suites.frontend.bpu.abtb.checker.assertions import matching_entry
from suites.frontend.bpu.abtb.checker.assertions import train_conditional_direction
from suites.frontend.bpu.abtb.checker.assertions import train_taken
from suites.frontend.bpu.abtb.case.definitions import BranchVector
from suites.frontend.bpu.abtb.case.definitions import HASH_SET_PC
from suites.frontend.bpu.runtime.paths import REPO_ROOT


SETS = range(48, 52)
BANKS = range(4)
PC = HASH_SET_PC + 2 * SETS.start


def _path_hash(set_index: int, bank: int) -> int:
    return ((set_index - SETS.start) << 2) | bank


@pytest.mark.feature("BPU-ABTB-046")
async def test_high_set_hash_grid_keeps_sixteen_counter_cells_isolated(abtb_agent):
    coverage = abtb_high_hash_grid_coverage_model()
    await abtb_agent.reset()
    vectors = {
        (set_index, bank): BranchVector(
            pc=PC,
            target=0x4009_0000 + set_index * 0x100 + bank * 0x20,
            position=4,
            branch_type=1,
        )
        for set_index in SETS
        for bank in BANKS
    }
    ways = {}
    expected = {}

    for (set_index, bank), vector in vectors.items():
        path_hash = _path_hash(set_index, bank)
        cold = await abtb_agent.predict(PC, path_hash=path_hash)
        assert_miss(cold)
        assert (cold.meta["setIdx"], cold.meta["bankMask"]) == (
            set_index, 1 << bank,
        )
        await train_taken(abtb_agent, vector, cold.meta)
        observed = await assert_conditional_state(
            abtb_agent, vector, taken=1, path_hash=path_hash
        )
        way, _ = matching_entry(observed, vector.position, vector.branch_type)
        ways[(set_index, bank)] = way
        expected[(set_index, bank)] = 1

    async def assert_grid() -> None:
        for (set_index, bank), vector in vectors.items():
            observed = await assert_conditional_state(
                abtb_agent,
                vector,
                taken=expected[(set_index, bank)],
                path_hash=_path_hash(set_index, bank),
            )
            assert (observed.meta["setIdx"], observed.meta["bankMask"]) == (
                set_index, 1 << bank,
            )
            assert sum(entry.valid for entry in observed.entries) == 1
            way, _ = matching_entry(observed, vector.position, vector.branch_type)
            assert way == ways[(set_index, bank)]

    await assert_grid()
    for (set_index, bank), vector in vectors.items():
        path_hash = _path_hash(set_index, bank)
        current = await abtb_agent.predict(PC, path_hash=path_hash)
        current = await age_conditional_to_not_taken(
            abtb_agent, vector, current, path_hash=path_hash
        )
        expected[(set_index, bank)] = 0
        await assert_grid()
        coverage.sample({
            "route": f"set_{set_index}_bank_{bank}",
            "direction": f"set_{set_index}_bank_{bank}_negative",
        })

        for direction in (0, 1, 1, 1):
            await train_conditional_direction(
                abtb_agent, vector, current, taken=1
            )
            current = await assert_conditional_state(
                abtb_agent, vector, taken=direction, path_hash=path_hash
            )
        expected[(set_index, bank)] = 1
        await assert_grid()
        coverage.sample({
            "route": f"set_{set_index}_bank_{bank}",
            "direction": f"set_{set_index}_bank_{bank}_positive",
        })

    coverage.assert_coverage(100.0)
    write_abtb_high_hash_grid_coverage(coverage, REPO_ROOT)
