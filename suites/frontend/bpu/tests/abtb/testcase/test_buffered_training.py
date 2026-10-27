"""A read-priority bank must retain fastTrain writes until reads stop."""

from __future__ import annotations

import pytest

from bpuverify.abtb.transaction.types import AbtbTraining
from bpuverify.abtb.coverage.catalog import abtb_buffered_training_coverage_model
from bpuverify.abtb.coverage.catalog import write_abtb_buffered_training_coverage
from bpuverify.abtb.checker.assertions import assert_miss
from bpuverify.abtb.checker.assertions import assert_vector_hit
from bpuverify.abtb.case.definitions import hash_set_vectors
from bpuverify.common.env.paths import REPO_ROOT


@pytest.mark.feature("BPU-ABTB-029")
async def test_two_train_writes_survive_same_bank_read_pressure(abtb_agent):
    coverage = abtb_buffered_training_coverage_model()
    await abtb_agent.reset()
    contexts = hash_set_vectors()[:2]
    cold_metadata = []
    for path_hash, vector in contexts:
        cold = await abtb_agent.predict(vector.pc, path_hash=path_hash)
        assert_miss(cold)
        assert cold.meta["bankMask"] == 8
        cold_metadata.append(cold.meta)
    assert [meta["setIdx"] for meta in cold_metadata] == [0, 1]

    # The lookup driver's idle state continues reading bank 3. Both accepted
    # trainings must remain pending rather than disappearing under read load.
    for (_, vector), meta in zip(contexts, cold_metadata, strict=True):
        await abtb_agent.train_under_read_pressure(
            AbtbTraining(
                pc=vector.pc,
                target=vector.target,
                taken=1,
                position=vector.position,
                branch_type=vector.branch_type,
                meta=meta,
            )
        )

    for (path_hash, vector), meta in zip(contexts, cold_metadata, strict=True):
        assert_miss(await abtb_agent.predict(vector.pc, path_hash=path_hash))
        coverage.sample({"set_phase": f"set_{meta['setIdx']}_pending"})

    await abtb_agent.drain_bank_writes()
    for (path_hash, vector), meta in zip(contexts, cold_metadata, strict=True):
        observed = await abtb_agent.predict(vector.pc, path_hash=path_hash)
        assert_vector_hit(observed, vector)
        assert (observed.meta["setIdx"], observed.meta["bankMask"]) == (
            meta["setIdx"],
            8,
        )
        coverage.sample({"set_phase": f"set_{meta['setIdx']}_committed"})

    coverage.assert_coverage(100.0)
    write_abtb_buffered_training_coverage(coverage, REPO_ROOT)
