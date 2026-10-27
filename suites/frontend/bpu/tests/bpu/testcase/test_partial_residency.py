"""A key that no longer resides must not learn from its former position's owner."""
import pytest

from bpuverify.bpu.case.partial_residency import check_partial_residency
from bpuverify.bpu.coverage.partial_residency import PartialResidencyCoverage
from bpuverify.bpu.model.tage.partial_residency import PROGRAMS


@pytest.mark.parametrize('program', tuple(pytest.param(p, id=p.name, marks=pytest.mark.feature(p.feature))
                                        for p in PROGRAMS))
async def test_old_feedback_distinguishes_resident_identity_from_evicted_key_reinstallation(
        bpu_agent, bpu_sc_output, program):
    coverage = PartialResidencyCoverage(program)
    try:
        await check_partial_residency(bpu_agent, program, coverage)
    finally:
        coverage.write(bpu_sc_output)
