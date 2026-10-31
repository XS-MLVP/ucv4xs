"""Intent-only state/address/overlap checks; reusable agents own all timing."""
import pytest

from suites.frontend.bpu.abtb.case.state.scenarios import check_counter_matrix
from suites.frontend.bpu.abtb.case.state.scenarios import check_replacer_matrix
from suites.frontend.bpu.abtb.case.state.scenarios import check_reset_training_priority
from suites.frontend.bpu.abtb.case.state.scenarios import check_writebuffer_capacity


@pytest.mark.feature('BPU-ABTB-049')
@pytest.mark.parametrize('bank', range(4))
async def test_full_counter_transition_and_feedback_gate_matrix(abtb_agent, abtb_state_output, bank):
    await check_counter_matrix(abtb_agent, abtb_state_output, bank=bank)


@pytest.mark.feature('BPU-ABTB-050')
@pytest.mark.estimated_runtime(290)
@pytest.mark.parametrize('bank', range(4))
@pytest.mark.parametrize('same_set', (True, False))
async def test_full_replacer_concurrent_port_matrix(abtb_agent, abtb_state_output, bank, same_set):
    await check_replacer_matrix(abtb_agent, abtb_state_output, bank=bank, same_set=same_set)


@pytest.mark.feature('BPU-ABTB-051')
@pytest.mark.parametrize('bank', range(4))
async def test_same_cell_counter_reset_training_priority(abtb_agent, abtb_state_output, bank):
    await check_reset_training_priority(abtb_agent, abtb_state_output, bank=bank)


@pytest.mark.feature('BPU-ABTB-052')
@pytest.mark.parametrize('bank', range(4))
async def test_four_slot_writebuffer_full_payload_lifecycle(abtb_agent, abtb_state_output, bank):
    await check_writebuffer_capacity(abtb_agent, abtb_state_output, bank=bank)
