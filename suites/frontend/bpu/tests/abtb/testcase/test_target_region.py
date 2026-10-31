"""AheadBTB partial targets at the generated 4 MiB region boundary."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.abtb.coverage.catalog import abtb_target_region_coverage_model
from suites.frontend.bpu.abtb.coverage.catalog import write_abtb_target_region_coverage
from suites.frontend.bpu.abtb.checker.assertions import assert_miss
from suites.frontend.bpu.abtb.checker.assertions import matching_entry
from suites.frontend.bpu.abtb.checker.assertions import train_taken
from suites.frontend.bpu.abtb.case.definitions import BranchVector
from suites.frontend.bpu.runtime.paths import REPO_ROOT


POSITION = 4
INDIRECT = 3
CASES = (
    ("fit", 0x407F_FFE0, 0x407F_FF00, 0x407F_FF00),
    ("overflow_wrap", 0x407F_FFE0, 0x4080_0100, 0x4040_0100),
    ("underflow_wrap", 0x4080_0000, 0x407F_FF00, 0x40BF_FF00),
)


@pytest.mark.feature("BPU-ABTB-032")
async def test_target_region_encoding_matches_disabled_carry_fix(abtb_agent):
    coverage = abtb_target_region_coverage_model()
    for region, pc, full_target, local_target in CASES:
        await abtb_agent.reset()
        cold = await abtb_agent.predict(pc)
        assert_miss(cold)

        vector = BranchVector(pc, full_target, POSITION, INDIRECT)
        await train_taken(abtb_agent, vector, cold.meta)
        observed = await abtb_agent.predict(pc)
        _, entry = matching_entry(observed, POSITION, INDIRECT)
        assert (entry.taken, entry.target) == (1, local_target), (
            region, vector, observed
        )
        coverage.sample({"target_region": region})

    coverage.assert_coverage(100.0)
    write_abtb_target_region_coverage(coverage, REPO_ROOT)
