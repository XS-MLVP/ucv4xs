"""Behavioral minimal control for integrated fast/resolve confidence loss."""
import pytest

from suites.frontend.bpu.ubtb.env.target_errors import check_adjacent_wrong_targets


@pytest.mark.feature('BPU-UBTB-011')
@pytest.mark.parametrize('second_source',('fast',pytest.param('resolve',marks=pytest.mark.feature('BPU-UBTB-017'))))
async def test_adjacent_wrong_targets_each_weaken_the_same_original_record(ubtb_agent,second_source):
    await check_adjacent_wrong_targets(ubtb_agent,second_source)
