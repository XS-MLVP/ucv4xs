"""RAS action API hides pulse width and branch-attribute encoding."""

from __future__ import annotations

from bpuverify.ras.model.addresses import return_addr
from bpuverify.ras.case.definitions import CALL_A


async def test_call_action_encodes_architectural_return_address(ras_agent):
    await ras_agent.reset()
    state = await ras_agent.act(
        2,
        start_pc=CALL_A.start_pc,
        position=CALL_A.position,
    )
    assert state.top == return_addr(CALL_A.start_pc, CALL_A.position)
