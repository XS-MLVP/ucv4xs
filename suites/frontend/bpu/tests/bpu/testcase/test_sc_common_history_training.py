"""Intent only: real common-history qualification gates all five SC tables."""
from itertools import product
import pytest
from suites.frontend.bpu.bpu.case.sc.history import check_history_training
from suites.frontend.bpu.bpu.coverage.sc.history import coverage as history_training_coverage

@pytest.mark.feature('BPU-INT-042')
@pytest.mark.parametrize('bank,valid', tuple(product((0, 1), (0, 1))))
async def test_actual_common_history_controls_all_table_updates(bpu_agent, bpu_sc_output, bank, valid):
    await check_history_training(bpu_agent, bpu_sc_output, dict(bank=bank, common_valid=valid),
        history_training_coverage())
