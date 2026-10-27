"""Same-PC replacement in one history bank preserves the other banks."""

from __future__ import annotations

import pytest

from bpuverify.abtb.coverage.catalog import abtb_cross_bank_replacement_coverage_model
from bpuverify.abtb.coverage.catalog import write_abtb_cross_bank_replacement_coverage
from bpuverify.abtb.checker.assertions import assert_miss
from bpuverify.abtb.checker.assertions import assert_position_profile
from bpuverify.abtb.checker.assertions import fill_taken_position_set
from bpuverify.abtb.checker.assertions import matching_entry
from bpuverify.abtb.checker.assertions import maybe_matching_entry
from bpuverify.abtb.checker.assertions import train_conditional_direction
from bpuverify.abtb.checker.assertions import train_taken
from bpuverify.abtb.case.definitions import NUM_WAYS
from bpuverify.abtb.case.definitions import same_pc_position_vectors
from bpuverify.common.env.paths import REPO_ROOT


PHYSICAL_SET = 2
BANKS = range(4)


@pytest.mark.feature("BPU-ABTB-042")
async def test_full_set_replacement_isolated_across_history_banks(abtb_agent):
    coverage = abtb_cross_bank_replacement_coverage_model()
    await abtb_agent.reset()
    vectors = {
        bank: same_pc_position_vectors(bank, PHYSICAL_SET)
        for bank in BANKS
    }
    assert len({branch.pc for group in vectors.values() for branch in group}) == 1
    pc = vectors[0][0].pc
    profiles = {}
    evicted = {bank: [] for bank in BANKS}

    async def assert_all_banks() -> None:
        for observed_bank in BANKS:
            prediction = await abtb_agent.predict(pc, path_hash=observed_bank)
            assert (prediction.meta["setIdx"], prediction.meta["bankMask"]) == (
                PHYSICAL_SET, 1 << observed_bank,
            )
            assert_position_profile(prediction, profiles[observed_bank])
            for old in evicted[observed_bank]:
                assert maybe_matching_entry(
                    prediction, old.position, old.branch_type
                ) is None

    for bank in BANKS:
        cold = await abtb_agent.predict(pc, path_hash=bank)
        assert_miss(cold)
        assert (cold.meta["setIdx"], cold.meta["bankMask"]) == (
            PHYSICAL_SET, 1 << bank,
        )
        full, way_by_position = await fill_taken_position_set(
            abtb_agent, vectors[bank][:NUM_WAYS], path_hash=bank
        )
        assert (full.meta["setIdx"], full.meta["bankMask"]) == (
            PHYSICAL_SET, 1 << bank,
        )
        profiles[bank] = {
            branch.position: (branch, way_by_position[branch.position], 1)
            for branch in vectors[bank][:NUM_WAYS]
        }

    await assert_all_banks()
    for bank in BANKS:
        before = await abtb_agent.predict(pc, path_hash=bank)
        late = vectors[bank][NUM_WAYS]
        await train_taken(abtb_agent, late, before.meta)
        after = await abtb_agent.predict(pc, path_hash=bank)
        new_way, new_entry = matching_entry(
            after, late.position, late.branch_type
        )
        assert (new_entry.taken, new_entry.target) == (1, late.target)

        survivors = {}
        for position, (branch, way, _) in profiles[bank].items():
            match = maybe_matching_entry(after, position, branch.branch_type)
            if match is None:
                evicted[bank].append(branch)
                assert way == new_way
            else:
                assert match[0] == way
                survivors[position] = (branch, way, 0)
        assert len(evicted[bank]) == 1
        assert len(survivors) == NUM_WAYS - 1
        profiles[bank] = {**survivors, late.position: (late, new_way, 1)}
        await assert_all_banks()
        coverage.sample({"transition": f"bank_{bank}_replacement"})

        # Not-taken feedback ages all four conditional hits, including the
        # newly allocated way. Recover them by position to exercise every
        # physical counter while the three other banks retain their profiles.
        earliest = min(survivors.values(), key=lambda item: item[0].position)[0]
        await train_conditional_direction(abtb_agent, earliest, after, taken=0)
        profiles[bank] = {
            position: (branch, way, 0)
            for position, (branch, way, _) in profiles[bank].items()
        }
        await assert_all_banks()
        coverage.sample({"transition": f"bank_{bank}_aged"})

        for branch in sorted(
            (item[0] for item in profiles[bank].values()),
            key=lambda item: item.position,
        ):
            # The survivors saw both replacement suppression and the aging
            # feedback, reaching strongly not-taken. The new entry only saw
            # the aging feedback and needs one taken update to recover.
            updates = 1 if branch == late else 2
            for attempt in range(updates):
                current = await abtb_agent.predict(pc, path_hash=bank)
                await train_taken(abtb_agent, branch, current.meta)
                profiles[bank] = {
                    position: (
                        vector,
                        way,
                        int(position == branch.position and attempt == updates - 1),
                    )
                    for position, (vector, way, _) in profiles[bank].items()
                }
                await assert_all_banks()
            way = profiles[bank][branch.position][1]
            coverage.sample({"transition": f"bank_{bank}_way_{way}_recovered"})

    coverage.assert_coverage(100.0)
    write_abtb_cross_bank_replacement_coverage(coverage, REPO_ROOT)
