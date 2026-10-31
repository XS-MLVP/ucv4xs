"""Six semantic fault contexts, with no slot enumeration or edge knowledge."""
import json
import pytest

from suites.frontend.bpu.runtime.artifacts import output_path
from suites.frontend.bpu.runtime.paths import REPO_ROOT
from suites.frontend.bpu.ras.case.retirement_gap import check_gap
from suites.frontend.bpu.ras.coverage.supplemental import RETIREMENT_GAP_CONTRACTS
from suites.frontend.bpu.ras.coverage.supplemental import ras_retirement_gap_coverage_model
from suites.frontend.bpu.ras.coverage.supplemental import write_ras_scenario_coverage


@pytest.mark.feature('BPU-RAS-016')
async def test_dropped_call_retirements_preserve_bos_boundaries(ras_agent):
    coverage, summaries = ras_retirement_gap_coverage_model(), []
    async with ras_agent.observe_committed() as observations:
        for epoch in ('same', 'cross'):
            for kind in ('threshold-hold', 'gap-reclaim', 'push-priority'):
                summaries.append(await check_gap(ras_agent, observations, epoch=epoch, kind=kind))
                for contract in RETIREMENT_GAP_CONTRACTS:
                    coverage.sample(dict(epoch=epoch, kind=kind, contract=contract))
                observations.clear()
    coverage.assert_coverage(100.0)
    write_ras_scenario_coverage(coverage, REPO_ROOT, 'retirement-gap')
    output = output_path(REPO_ROOT / 'results/ras/retirement-gap-summary.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(dict(feature='BPU-RAS-016', summaries=summaries), indent=2) + '\n')
