"""Only scenario intent; drivers/monitors/models own pins, timing and checking."""
import pytest
from suites.frontend.bpu.bpu.case.abtb.cases import check_counter_case

pytestmark = pytest.mark.abtb_counter_matrix


@pytest.mark.feature('BPU-INT-055')
@pytest.mark.estimated_runtime(240)
async def test_integrated_abtb_five_alias_four_way_reuse(bpu_agent, bpu_sc_output, bank, entry_set):
    await check_counter_case(bpu_agent, bpu_sc_output,
        kind='five_alias', bank=bank, entry_set=entry_set)


@pytest.mark.feature('BPU-INT-056')
@pytest.mark.estimated_runtime(800)
async def test_integrated_abtb_true_final_not_taken(bpu_agent, bpu_sc_output, bank, entry_set):
    await check_counter_case(bpu_agent, bpu_sc_output,
        kind='final_not_taken', bank=bank, entry_set=entry_set)


@pytest.mark.feature('BPU-INT-058')
@pytest.mark.estimated_runtime(800)
async def test_integrated_abtb_later_taken_four_way_paths(bpu_agent, bpu_sc_output, bank, entry_set):
    await check_counter_case(bpu_agent, bpu_sc_output,
        kind='later_taken', bank=bank, entry_set=entry_set)
