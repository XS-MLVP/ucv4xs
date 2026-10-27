"""Upper folded-history index bits select distinct sets within one bank."""

from __future__ import annotations

import pytest

from bpuverify.abtb.coverage.catalog import abtb_hash_set_coverage_model
from bpuverify.abtb.coverage.catalog import write_abtb_hash_set_coverage
from bpuverify.abtb.checker.assertions import assert_miss
from bpuverify.abtb.checker.assertions import assert_vector_hit
from bpuverify.abtb.checker.assertions import train_taken
from bpuverify.abtb.case.definitions import hash_set_vectors
from bpuverify.common.env.paths import REPO_ROOT


@pytest.mark.feature("BPU-ABTB-025")
async def test_same_pc_uses_hash_selected_sets_without_cross_set_alias(abtb_agent):
    coverage = abtb_hash_set_coverage_model()
    await abtb_agent.reset()
    vectors = hash_set_vectors()
    for set_index, (path_hash, vector) in enumerate(vectors):
        cold = await abtb_agent.predict(vector.pc, path_hash=path_hash)
        assert_miss(cold)
        assert (cold.meta["setIdx"], cold.meta["bankMask"]) == (set_index, 8)
        await train_taken(abtb_agent, vector, cold.meta)

    for set_index, (path_hash, vector) in enumerate(vectors):
        observed = await abtb_agent.predict(vector.pc, path_hash=path_hash)
        assert_vector_hit(observed, vector)
        assert (observed.meta["setIdx"], observed.meta["bankMask"]) == (
            set_index, 8
        )
        coverage.sample({"set_index": set_index})
    coverage.assert_coverage(100.0)
    write_abtb_hash_set_coverage(coverage, REPO_ROOT)
