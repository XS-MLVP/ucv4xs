"""Return-and-call is pop then push at each public RAS event boundary."""
from copy import deepcopy

import pytest


async def committed_prefix(agent):
    await agent.reset()
    for pc in (0x40001000, 0x40002000):
        before = deepcopy(agent.snapshot().commit_meta)
        await agent.act(2, start_pc=pc, position=3)
        await agent.commit(before, action=2)
    return agent.snapshot()


@pytest.mark.feature('BPU-RAS-017')
async def test_speculative_return_and_call_replaces_only_the_youngest_frame(ras_agent):
    await committed_prefix(ras_agent)
    actual = await ras_agent.act(3, start_pc=0x40003000, position=3)
    assert actual.top == 0x40003008 // 2
    assert (await ras_agent.act(1)).top == 0x40001008 // 2


@pytest.mark.feature('BPU-RAS-017')
async def test_recovery_return_and_call_restores_before_redo(ras_agent):
    saved = await committed_prefix(ras_agent)
    await ras_agent.act(2, start_pc=0x40009000, position=3)
    actual = await ras_agent.recover(saved.redirect_meta, action=3, cfi_pc=0x40003006)
    assert actual.top == 0x40003008 // 2
    assert (await ras_agent.act(1)).top == 0x40001008 // 2


@pytest.mark.feature('BPU-RAS-017')
async def test_resolved_return_and_call_retires_real_source_address(ras_agent):
    """Standalone commit-attribute correction, not a full FTQ legality trace.

    The speculative call supplies its real address and genuine pre-operation
    metadata. The resolved attribute requests pop+push. A later return must
    consume committed C instead of the old B; a live speculative C alone does
    not prove that the combined retirement updated the committed stack.
    """
    saved = await committed_prefix(ras_agent)
    await ras_agent.act(2, start_pc=0x40003000, position=3)
    await ras_agent.commit(saved.commit_meta, action=3)
    actual = await ras_agent.act(1)
    assert actual.top == 0x40003008 // 2
    assert (await ras_agent.act(1)).top == 0x40001008 // 2
