"""Logical RAS scenarios; agent/model/monitor own details and comparisons."""
from suites.frontend.bpu.models.configuration import *
import pytest

from suites.frontend.bpu.ras.coverage.supplemental import ras_committed_cells_coverage_model
from suites.frontend.bpu.ras.coverage.supplemental import ras_adjacent_coverage_model
from suites.frontend.bpu.ras.coverage.supplemental import ras_redirect_redo_coverage_model
from suites.frontend.bpu.ras.coverage.supplemental import write_ras_scenario_coverage
from suites.frontend.bpu.ras.case.adjacent_cases import cases
from suites.frontend.bpu.ras.case.committed_cells_scenario import check_case
from suites.frontend.bpu.ras.case.adjacent_scenario import check_burst
from suites.frontend.bpu.ras.case.redirect_redo_scenario import check_redirect
from suites.frontend.bpu.runtime.paths import REPO_ROOT


@pytest.mark.feature('BPU-RAS-013')
async def test_committed_cells(ras_agent):
    coverage = ras_committed_cells_coverage_model()
    async with ras_agent.observe_committed() as observations:
        for slot in range(RAS_GROUPS):
            for mode in ('normal', 'saturated'):
                await check_case(ras_agent, observations, slot=slot, mode=mode)
                coverage.sample(dict(slot=slot, mode=mode))
                observations.clear()
    coverage.assert_coverage(100.0)
    write_ras_scenario_coverage(coverage, REPO_ROOT, 'committed-cells')


@pytest.mark.feature('BPU-RAS-014')
async def test_adjacent_operations(ras_agent):
    coverage = ras_adjacent_coverage_model()
    async with ras_agent.observe_committed() as observations:
        for case in cases():
            await check_burst(ras_agent, observations, **case)
            coverage.sample(dict(scenario=case['label']))
            observations.clear()
    coverage.assert_coverage(100.0)
    write_ras_scenario_coverage(coverage, REPO_ROOT, 'adjacent-operations')


@pytest.mark.feature('BPU-RAS-015')
async def test_redirect_redo(ras_agent):
    coverage = ras_redirect_redo_coverage_model()
    async with ras_agent.observe_committed() as observations:
        for storage in ('inflight', 'committed'):
            for counter in (0, 3, 7):
                for redo in ('call-same', 'call-distinct-positive', 'call-distinct-negative', 'return'):
                    await check_redirect(ras_agent, observations, storage=storage, counter=counter, redo=redo)
                    coverage.sample(dict(storage=storage, counter=counter, redo=redo))
                    observations.clear()
    coverage.assert_coverage(100.0)
    write_ras_scenario_coverage(coverage, REPO_ROOT, 'redirect-redo')
