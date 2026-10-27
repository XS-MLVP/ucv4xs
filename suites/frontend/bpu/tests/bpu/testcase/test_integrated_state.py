"""Intent-only integration scenarios; reusable drivers/monitors own timing and checking."""
import pytest
from bpuverify.bpu.case.bypass.cases import check_integrated_case
from bpuverify.bpu.case.ras.cases import check_retirement_case


@pytest.mark.feature('BPU-INT-044')
@pytest.mark.parametrize('bank', (0, 1))
async def test_natural_abtb_microtage_loop(bpu_agent, bpu_sc_output, bank):
    await check_integrated_case(bpu_agent, bpu_sc_output, kind='natural', bank=bank)


@pytest.mark.feature('BPU-INT-045')
async def test_lower_shadow_ring_wrap(bpu_agent, bpu_sc_output):
    await check_integrated_case(bpu_agent, bpu_sc_output, kind='lower')


@pytest.mark.feature('BPU-INT-046')
async def test_full_sram_reset_and_writeback(bpu_agent, bpu_sc_output):
    await check_integrated_case(bpu_agent, bpu_sc_output, kind='sram')


@pytest.mark.feature('BPU-INT-047')
async def test_upper_force_writeback_and_public_return(bpu_agent, bpu_sc_output):
    await check_integrated_case(bpu_agent, bpu_sc_output, kind='force')


@pytest.mark.feature('BPU-INT-048')
@pytest.mark.parametrize('kind,bank', (('history', 2), ('history', 3), ('alternate', 1)))
async def test_nonzero_history_training_sources(bpu_agent, bpu_sc_output, kind, bank):
    await check_integrated_case(bpu_agent, bpu_sc_output, kind=kind, bank=bank)


@pytest.mark.feature('BPU-INT-049')
async def test_two_program_full_shadow_eviction_and_sram_return(bpu_agent, bpu_sc_output):
    await check_integrated_case(bpu_agent, bpu_sc_output, kind='two_program', bank=1)


@pytest.mark.feature('BPU-INT-050')
async def test_parent_training_policy_from_public_metadata(bpu_agent, bpu_sc_output):
    await check_integrated_case(bpu_agent, bpu_sc_output, kind='policy', bank=1)


@pytest.mark.feature('BPU-INT-051')
@pytest.mark.estimated_runtime(1340)
async def test_natural_failed_allocation_reaches_useful_aging(bpu_agent, bpu_sc_output):
    await check_integrated_case(bpu_agent, bpu_sc_output, kind='aging', bank=1)


@pytest.mark.feature('BPU-INT-052')
async def test_actual_s3_metadata_retirement_nested_calls_returns(bpu_agent, bpu_sc_output):
    await check_retirement_case(bpu_agent, bpu_sc_output, kind='nested')


@pytest.mark.feature('BPU-INT-053')
@pytest.mark.parametrize('depth', (4, 7, 8))
async def test_retirement_crosses_all_committed_stack_slots(bpu_agent, bpu_sc_output, depth):
    await check_retirement_case(bpu_agent, bpu_sc_output, kind='deep', count=depth)


@pytest.mark.feature('BPU-INT-054')
@pytest.mark.parametrize('count', (9, 10))
async def test_repeat_retirement_saturates_and_splits_entry(bpu_agent, bpu_sc_output, count):
    await check_retirement_case(bpu_agent, bpu_sc_output, kind='repeat', count=count)
