"""A stale but genuine prediction snapshot can allocate the same branch twice."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.abtb.transaction.types import AbtbTraining
from suites.frontend.bpu.abtb.coverage.catalog import abtb_multi_hit_coverage_model
from suites.frontend.bpu.abtb.coverage.catalog import write_abtb_multi_hit_coverage
from suites.frontend.bpu.abtb.checker.assertions import assert_miss
from suites.frontend.bpu.abtb.checker.assertions import matching_entry
from suites.frontend.bpu.abtb.case.definitions import CONDITIONAL
from suites.frontend.bpu.abtb.case.definitions import DIRECT
from suites.frontend.bpu.runtime.paths import REPO_ROOT


@pytest.mark.feature("BPU-ABTB-028")
async def test_stale_training_multi_hit_is_detected_and_cleaned(abtb_agent):
    coverage = abtb_multi_hit_coverage_model()

    for vector, bank in ((CONDITIONAL, 0), (DIRECT, 2)):
        await abtb_agent.reset()
        cold = await abtb_agent.predict(vector.pc, path_hash=bank)
        assert_miss(cold)
        assert cold.meta["bankMask"] == 1 << bank
        training = AbtbTraining(
            pc=vector.pc,
            target=vector.target,
            taken=1,
            position=vector.position,
            branch_type=vector.branch_type,
            meta=cold.meta,
        )

        await abtb_agent.train(training)
        first = await abtb_agent.predict(vector.pc, path_hash=bank)
        first_way, _ = matching_entry(first, vector.position, vector.branch_type)

        # The same real cold snapshot may be held by a second in-flight FTQ
        # entry. Reusing it misses the new way and allocates another way.
        await abtb_agent.train(training)
        duplicate = await abtb_agent.predict(vector.pc, path_hash=bank)
        duplicate_ways = {
            way for way, entry in enumerate(duplicate.entries)
            if entry.valid
            and entry.position == vector.position
            and entry.branch_type == vector.branch_type
            and entry.target == vector.target
        }
        assert len(duplicate_ways) == 2, (vector, duplicate)
        assert first_way in duplicate_ways
        coverage.sample({"bank_phase": f"bank_{bank}_duplicate"})

        # Reads outrank buffered writes in the single-port bank. The agent
        # provides a quiet window without exposing driver or edge details.
        await abtb_agent.drain_bank_writes()
        cleaned = await abtb_agent.predict(vector.pc, path_hash=bank)
        retained_way, retained = matching_entry(
            cleaned, vector.position, vector.branch_type
        )
        assert retained_way in duplicate_ways - {first_way}, (vector, cleaned)
        assert (retained.taken, retained.target) == (1, vector.target)
        coverage.sample({"bank_phase": f"bank_{bank}_cleaned"})

    coverage.assert_coverage(100.0)
    write_abtb_multi_hit_coverage(coverage, REPO_ROOT)
