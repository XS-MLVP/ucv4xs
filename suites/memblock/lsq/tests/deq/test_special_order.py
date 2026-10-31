import pytest

from suites.memblock.lsq.deq.agent import PsqAgent
from suites.memblock.lsq.deq.types import Store


@pytest.mark.parametrize("memory", (1, 2, 7))
async def test_completed_special_cannot_release_older_stalled_sbuffer_owner(deq_full, memory):
    agent = PsqAgent(deq_full)
    old = agent.add(Store(vaddr=0x30000, page=0xABC, byte_mask=255, data=0x8877665544332211,
                          data_valid=True, address_valid=True, committed=True))
    special = agent.add(Store(vaddr=0x40000, page=0xDEF, byte_mask=255, data=0x1111222233334444,
                              memory_type=memory, data_valid=True, address_valid=True, committed=True))
    for _ in range(12):
        await agent.step(sbuffer_ready=(False, False))
        if agent.owners.get(1) is not None and agent.owners[1].finished:
            break
    assert old not in agent.completed and agent.owners[1].finished
    deq_full.coverage.sample(("DEQ-CREDIT.special_order",), deq_full.last_tick)
    await agent.step(sbuffer_ready=(False, False))
    await agent.drain()
    agent.checked(("DEQ-CREDIT.special_order",), [old, special])
