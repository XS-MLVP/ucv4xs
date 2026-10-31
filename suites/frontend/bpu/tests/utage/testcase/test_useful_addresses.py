"""Complete address requirements; driver/model/monitor own timing and checking."""

from suites.frontend.bpu.runtime.artifacts import output_path
from suites.frontend.bpu.runtime.artifacts import write_output
import json

import pytest

from suites.frontend.bpu.utage.case.errors import UtageUsefulProviderBlocked
from suites.frontend.bpu.utage.coverage.supplemental import utage_useful_allocation_coverage_model
from suites.frontend.bpu.utage.coverage.supplemental import utage_useful_update_coverage_model
from suites.frontend.bpu.utage.coverage.supplemental import utage_partial_wrap_coverage_model
from suites.frontend.bpu.utage.coverage.supplemental import write_utage_address_coverage
from suites.frontend.bpu.runtime.paths import REPO_ROOT
from suites.frontend.bpu.utage.case.useful_address_scenario import check_allocation_routes
from suites.frontend.bpu.utage.case.useful_address_scenario import check_update_routes
from suites.frontend.bpu.utage.case.partial_wrap_scenario import check_partial_wrap


@pytest.mark.feature('BPU-UTAGE-020')
async def test_useful_allocation_address_matrix(utage_agent):
    coverage = utage_useful_allocation_coverage_model()
    await check_allocation_routes(utage_agent, coverage, REPO_ROOT / 'results/utage')
    coverage.assert_coverage(100.0)
    write_utage_address_coverage(coverage, REPO_ROOT, 'useful-allocation')


@pytest.mark.feature('BPU-UTAGE-021')
@pytest.mark.estimated_runtime(650)
async def test_useful_update_full_required_address_matrix(utage_agent):
    # The whole-chip DefaultConfig reconstructs the upper tag bits from the
    # start PC on read, so the eight stored tag bits do not block any of the
    # 512 lower-provider update contexts.  The former strict XFAIL for
    # UTAGE-007 is retained as the runtime `blocked` report below; if a build
    # truly truncates the comparison, this becomes a real FAIL again.
    coverage = utage_useful_update_coverage_model()
    blocked = await check_update_routes(utage_agent, coverage, REPO_ROOT / 'results/utage')
    write_utage_address_coverage(coverage, REPO_ROOT, 'useful-update')
    write_output(REPO_ROOT / 'results/utage/useful-update-blocked-providers.json',
        json.dumps(dict(blocked=blocked, declared_allowances=list(utage_agent.allowed_reference_events)),
                   indent=2) + '\n')
    if blocked:
        raise UtageUsefulProviderBlocked(f'{len(blocked)} required lower provider contexts blocked '
            f'by UTAGE-007; first={blocked[0]!r}')
    coverage.assert_coverage(100.0)


@pytest.mark.feature('BPU-UTAGE-022')
async def test_old_upper_slot_after_partial_wrap(utage_agent):
    coverage = utage_partial_wrap_coverage_model()
    for mode in ('serial', 'adjacent'):
        for bank in range(4):
            await check_partial_wrap(utage_agent, coverage, REPO_ROOT / 'results/utage', mode=mode, bank=bank)
    coverage.assert_coverage(100.0)
    write_utage_address_coverage(coverage, REPO_ROOT, 'partial-shadow-wrap')
