"""Same-region provider target and allocation reuse one region update pointer."""
import pytest

from suites.frontend.bpu.ittage.case.definitions import PC
from suites.frontend.bpu.ittage.case.definitions import POSITION
from suites.frontend.bpu.ittage.case.definitions import TARGET_A
from suites.frontend.bpu.ittage.transaction.types import IttageTraining

REGION = 0x410 << 20
T0, T1, T2 = REGION | 0x1200, REGION | 0x1400, REGION | 0x1600


async def wait_allocation(agent, table):
    for _ in range(128):
        prediction = await agent.predict(PC)
        offer = prediction.meta['allocate']
        if offer['valid'] == 1 and offer['bits'] == table:
            return prediction
    raise AssertionError(f'no allocation offer for table {table}')


@pytest.mark.feature('BPU-ITTAGE-018')
@pytest.mark.feature('BPU-ITTAGE-003')
async def test_same_region_provider_update_and_new_table_allocation_share_the_region_pointer(
    ittage_agent,
):
    await ittage_agent.reset()

    # Build a table-0 provider and then a table-1 provider, both targeting
    # distinct offsets in one non-PC region. The table-1 entry becomes the
    # provider and table 0 its alternate.
    first = await wait_allocation(ittage_agent, 0)
    await ittage_agent.train(IttageTraining(PC, POSITION, T0, first.meta, 1))
    second = await wait_allocation(ittage_agent, 1)
    await ittage_agent.train(IttageTraining(PC, POSITION, T1, second.meta, 1))

    trained = await ittage_agent.predict(PC)
    assert trained.meta['provider'] == {'bits': 1, 'valid': 1}, trained
    assert trained.meta['altProvider'] == {'bits': 0, 'valid': 1}, trained
    assert trained.meta['providerTarget_addr'] == T1
    assert trained.meta['altProviderTarget_addr'] == T0

    # A mispredicted same-region target allocates the last free table while
    # updating the table-1 provider. Both region update ports and the table
    # write refer to the already resident target region in this cycle.
    third = await wait_allocation(ittage_agent, 2)
    await ittage_agent.train(IttageTraining(PC, POSITION, T2, third.meta, 1))

    actual = await ittage_agent.predict(PC)
    assert actual.hit == 1 and actual.target == T2
    assert actual.meta['provider'] == {'bits': 2, 'valid': 1}, actual
    assert actual.meta['providerTarget_addr'] == T2
    assert actual.meta['providerCnt_value'] == 2, actual
    assert actual.meta['altProvider'] == {'bits': 1, 'valid': 1}, actual
    assert actual.meta['altProviderTarget_addr'] == T1, actual
    assert actual.meta['altProviderCnt_value'] == 1, actual
    assert TARGET_A not in (T0, T1, T2)
