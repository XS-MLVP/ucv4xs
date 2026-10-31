"""Dedicated AheadBTB functional-coverage closure scenario."""

from __future__ import annotations

from suites.frontend.bpu.abtb.coverage.catalog import abtb_coverage_model
from suites.frontend.bpu.abtb.coverage.catalog import write_abtb_coverage
from suites.frontend.bpu.abtb.checker.assertions import assert_miss
from suites.frontend.bpu.abtb.checker.assertions import assert_vector_hit
from suites.frontend.bpu.abtb.checker.assertions import train_taken
from suites.frontend.bpu.abtb.case.definitions import TRAINING_VECTORS
from suites.frontend.bpu.abtb.case.definitions import hash_bank_vectors
from suites.frontend.bpu.runtime.paths import REPO_ROOT


async def test_abtb_functional_coverage_closes_defined_bins(abtb_agent):
    coverage = abtb_coverage_model()
    await abtb_agent.reset()

    for vector in TRAINING_VECTORS:
        cold = await abtb_agent.predict(vector.pc)
        assert_miss(cold)
        coverage.sample(
            {
                "phase": "cold",
                "result": "miss",
                "branch_type": vector.branch_type,
                "bank_mask": cold.meta["bankMask"],
                "history_class": "zero",
            }
        )
        await train_taken(abtb_agent, vector, cold.meta)
        trained = await abtb_agent.predict(vector.pc)
        assert_vector_hit(trained, vector)
        coverage.sample(
            {
                "phase": "trained",
                "result": "hit",
                "branch_type": vector.branch_type,
                "bank_mask": trained.meta["bankMask"],
                "history_class": "zero",
            }
        )

    for path_hash, vector in hash_bank_vectors()[1:]:
        cold = await abtb_agent.predict(vector.pc, path_hash=path_hash)
        assert_miss(cold)
        assert cold.meta["bankMask"] == 1 << path_hash
        coverage.sample({
            "phase": "cold",
            "result": "miss",
            "branch_type": vector.branch_type,
            "bank_mask": cold.meta["bankMask"],
            "history_class": "nonzero",
        })
        await train_taken(abtb_agent, vector, cold.meta)
        trained = await abtb_agent.predict(vector.pc, path_hash=path_hash)
        assert_vector_hit(trained, vector)
        coverage.sample({
            "phase": "trained",
            "result": "hit",
            "branch_type": vector.branch_type,
            "bank_mask": trained.meta["bankMask"],
            "history_class": "nonzero",
        })

    coverage.assert_coverage(100.0)
    write_abtb_coverage(coverage, REPO_ROOT)
