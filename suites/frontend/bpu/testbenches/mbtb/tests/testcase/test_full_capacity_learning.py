"""Full-capacity retention in both input orders and communication modes."""
import pytest
from suites.frontend.bpu.testbenches.shared.env.artifacts import output_directory
from suites.frontend.bpu.testbenches.shared.env.paths import REPO_ROOT
from suites.frontend.bpu.testbenches.mbtb.tests.scenarios.full_capacity_learning import check_full_capacity_learning
from suites.frontend.bpu.testbenches.mbtb.coverage.full_capacity_learning import FullCapacityCoverage
from suites.frontend.bpu.testbenches.mbtb.model.full_capacity_learning import MODES
from suites.frontend.bpu.testbenches.mbtb.model.full_capacity_learning import ORDERS


@pytest.mark.feature('BPU-MBTB-017')
@pytest.mark.parametrize('mode', MODES)
@pytest.mark.parametrize('order', ORDERS)
async def test_full_set_keeps_both_new_branches_and_their_age_without_neighbor_corruption(mbtb_agent, mode, order):
    coverage = FullCapacityCoverage(mode, order)
    try:
        await check_full_capacity_learning(mbtb_agent, mode, order, coverage)
    finally:
        coverage.write(output_directory(REPO_ROOT, 'mbtb'))


@pytest.mark.feature('BPU-MBTB-017')
@pytest.mark.parametrize('mode', MODES)
@pytest.mark.parametrize('order', ORDERS)
async def test_full_set_new_positions_keep_chronological_victims_and_independent_neighbor_age(mbtb_agent, mode, order):
    coverage = FullCapacityCoverage(mode, order, position_relation='new-position')
    try:
        await check_full_capacity_learning(mbtb_agent, mode, order, coverage, position_relation='new-position')
    finally:
        coverage.write(output_directory(REPO_ROOT, 'mbtb'))
