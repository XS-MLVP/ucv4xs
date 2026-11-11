"""Restore a real checkpoint with independently supplied guarded CFI PC."""
from copy import deepcopy


async def check_guarded_call(agent, pc):
    await agent.reset()
    await agent.act(2, start_pc=0x40001000, position=3)
    checkpoint = agent.snapshot()
    frozen = deepcopy(checkpoint.redirect_meta)
    await agent.act(2, start_pc=0x40002000, position=5)
    actual = await agent.recover(checkpoint.redirect_meta, action=2, cfi_pc=pc)
    expected = ((pc + 2) % (1 << 51)) // 2
    assert actual.top == expected, 'restored guarded call address differs from the original input'
    assert checkpoint.redirect_meta == frozen
