"""Folded-history selection of independent AheadBTB banks."""

from __future__ import annotations

import pytest

from bpuverify.abtb.coverage.catalog import abtb_max_set_coverage_model
from bpuverify.abtb.coverage.catalog import write_abtb_max_set_coverage
from bpuverify.abtb.checker.assertions import assert_miss
from bpuverify.abtb.checker.assertions import assert_vector_hit
from bpuverify.abtb.checker.assertions import train_taken
from bpuverify.abtb.case.definitions import hash_bank_vectors
from bpuverify.abtb.case.definitions import highest_set_vectors
from bpuverify.common.env.paths import REPO_ROOT


@pytest.mark.feature("BPU-ABTB-012")
async def test_same_pc_uses_history_selected_bank_without_cross_bank_alias(abtb_agent):
    await abtb_agent.reset()
    vectors = hash_bank_vectors()
    for path_hash, vector in vectors:
        cold = await abtb_agent.predict(vector.pc, path_hash=path_hash)
        assert_miss(cold)
        assert cold.meta["setIdx"] == 0
        assert cold.meta["bankMask"] == 1 << path_hash
        await train_taken(abtb_agent, vector, cold.meta)

    for path_hash, vector in vectors:
        trained = await abtb_agent.predict(vector.pc, path_hash=path_hash)
        assert_vector_hit(trained, vector)


@pytest.mark.feature("BPU-ABTB-018")
async def test_highest_set_training_isolated_across_four_banks(abtb_agent):
    coverage = abtb_max_set_coverage_model()
    await abtb_agent.reset()
    vectors = tuple(
        (bank, highest_set_vectors(bank, 1)[0])
        for bank in range(4)
    )

    for bank, vector in vectors:
        cold = await abtb_agent.predict(vector.pc, path_hash=bank)
        assert_miss(cold)
        assert (cold.meta["setIdx"], cold.meta["bankMask"]) == (63, 1 << bank)
        await train_taken(abtb_agent, vector, cold.meta)

    for bank, vector in vectors:
        observed = await abtb_agent.predict(vector.pc, path_hash=bank)
        assert_vector_hit(observed, vector)
        assert (observed.meta["setIdx"], observed.meta["bankMask"]) == (
            63, 1 << bank
        )
        coverage.sample({"bank_mask": observed.meta["bankMask"]})

    coverage.assert_coverage(100.0)
    write_abtb_max_set_coverage(coverage, REPO_ROOT)
