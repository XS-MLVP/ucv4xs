"""Intent only: genuine conditional history, table learning and public readback."""
from itertools import product
import pytest
from bpuverify.bpu.case.sc.nonzero import check_nonzero_history
from bpuverify.bpu.coverage.sc.nonzero import coverage as nonzero_history_coverage

@pytest.mark.feature('BPU-INT-043')
@pytest.mark.parametrize('bank,direction', tuple(product((0, 1), ('forward', 'backward'))))
async def test_real_nonzero_history_trains_and_reads_back_all_SC_tables(bpu_agent, bpu_sc_output, bank, direction):
    await check_nonzero_history(bpu_agent, bpu_sc_output, dict(bank=bank, direction=direction),
        nonzero_history_coverage())
