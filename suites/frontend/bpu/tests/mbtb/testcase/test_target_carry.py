"""MainBTB reconstructs a partial target across its 2 MiB boundary."""

from __future__ import annotations

import pytest

from bpuverify.mbtb.coverage.catalog import mbtb_target_carry_coverage_model
from bpuverify.mbtb.coverage.catalog import write_mbtb_target_carry_coverage
from bpuverify.mbtb.checker.assertions import assert_miss
from bpuverify.mbtb.checker.assertions import assert_vector_hit
from bpuverify.mbtb.checker.assertions import train
from bpuverify.mbtb.case.definitions import BranchVector
from bpuverify.common.env.paths import REPO_ROOT


TARGET_REGION_SPAN = 1 << 20  # Encoded halfword addresses; 2 MiB in bytes.
REGION = 0x4000_0000
TARGET_CASES = (
    ("fit", BranchVector(REGION + 0x800, REGION + 0x1234, 3, 2)),
    (
        "overflow",
        BranchVector(REGION + TARGET_REGION_SPAN - 0x20,
                     REGION + TARGET_REGION_SPAN + 0x100, 3, 2),
    ),
    (
        "underflow",
        BranchVector(REGION + TARGET_REGION_SPAN,
                     REGION + TARGET_REGION_SPAN - 0x100, 3, 2),
    ),
)


@pytest.mark.feature("BPU-MBTB-013")
async def test_partial_target_fit_overflow_and_underflow(mbtb_agent):
    coverage = mbtb_target_carry_coverage_model()
    for direction, vector in TARGET_CASES:
        delta = vector.target // TARGET_REGION_SPAN - vector.pc // TARGET_REGION_SPAN
        assert delta == {"fit": 0, "overflow": 1, "underflow": -1}[direction]
        await mbtb_agent.reset()
        cold = await mbtb_agent.predict(vector.pc)
        assert_miss(cold)
        await train(mbtb_agent, vector, cold.meta_entries)
        actual = await mbtb_agent.predict(vector.pc)
        assert_vector_hit(actual, vector)
        coverage.sample({"case": direction})

    coverage.assert_coverage(100.0)
    write_mbtb_target_carry_coverage(coverage, REPO_ROOT)
