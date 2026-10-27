"""Dedicated MicroBTB functional-coverage closure scenario."""

from __future__ import annotations

from bpuverify.common.coverage.exports import write_functional_coverage

from bpuverify.common.env.artifacts import output_path

from toffee import CoverageDatabase

from bpuverify.ubtb.transaction.types import BranchTraining
from bpuverify.ubtb.coverage.catalog import ubtb_coverage_model
from bpuverify.ubtb.coverage.catalog import ubtb_useful_coverage_model
from bpuverify.common.env.paths import REPO_ROOT
from bpuverify.ubtb.checker.assertions import assert_hit
from bpuverify.ubtb.checker.assertions import assert_miss
from bpuverify.ubtb.checker.assertions import train_not_taken
from bpuverify.ubtb.checker.assertions import train_taken
from bpuverify.ubtb.case.definitions import BranchVector
from bpuverify.ubtb.case.definitions import DIRECT
from bpuverify.ubtb.case.definitions import NOT_TAKEN
from bpuverify.ubtb.case.definitions import random_training_vectors


async def test_ubtb_functional_coverage_closes_defined_bins(ubtb_agent):
    coverage = ubtb_coverage_model()
    usefulness = ubtb_useful_coverage_model()
    await ubtb_agent.reset()

    for vector in random_training_vectors():
        await assert_miss(ubtb_agent, vector.pc)
        coverage.sample(
            {"phase": "cold", "result": "miss", "branch_type": vector.branch_type}
        )
        await train_taken(ubtb_agent, vector)
        await assert_hit(ubtb_agent, vector)
        coverage.sample(
            {
                "phase": "trained",
                "result": "hit",
                "branch_type": vector.branch_type,
            }
        )

    await assert_miss(ubtb_agent, NOT_TAKEN.pc)
    await train_not_taken(ubtb_agent, NOT_TAKEN)
    await assert_miss(ubtb_agent, NOT_TAKEN.pc)
    coverage.sample(
        {"phase": "trained", "result": "miss", "branch_type": NOT_TAKEN.branch_type}
    )

    await ubtb_agent.reset()
    await train_taken(ubtb_agent, DIRECT)
    await assert_hit(ubtb_agent, DIRECT)
    usefulness.sample({"transition": "strong_hit"})

    not_taken = BranchTraining(
        pc=DIRECT.pc,
        target=DIRECT.target,
        taken=0,
        position=DIRECT.position,
        branch_type=DIRECT.branch_type,
    )
    await ubtb_agent.train(not_taken)
    await assert_hit(ubtb_agent, DIRECT)
    usefulness.sample({"transition": "aged_hit"})

    await train_taken(ubtb_agent, DIRECT)
    await assert_hit(ubtb_agent, DIRECT)
    usefulness.sample({"transition": "recovered_hit"})
    await train_taken(ubtb_agent, DIRECT)
    await assert_hit(ubtb_agent, DIRECT)
    usefulness.sample({"transition": "saturated_hit"})

    for _ in range(3):
        await ubtb_agent.train(not_taken)
    await assert_miss(ubtb_agent, DIRECT.pc)
    usefulness.sample({"transition": "invalid_miss"})

    replacement = BranchVector(
        DIRECT.pc, DIRECT.target + 0x100, DIRECT.position, DIRECT.branch_type
    )
    await train_taken(ubtb_agent, replacement)
    await assert_hit(ubtb_agent, replacement)
    usefulness.sample({"transition": "reallocated_hit"})

    coverage.assert_coverage(100.0)
    usefulness.assert_coverage(100.0)
    write_functional_coverage(CoverageDatabase([coverage, usefulness]), output_path(REPO_ROOT / "results" / "ubtb" / "functional-coverage.json"))
