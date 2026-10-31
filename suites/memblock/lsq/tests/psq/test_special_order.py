
import json
from pathlib import Path

import pytest

from suites.memblock.lsq.legacy_pins import P
from suites.memblock.lsq.psq.checks import read_ptr
from suites.memblock.lsq.psq.types import Address, Attributes, Data
from suites.memblock.lsq.raw.types import SqPtr
from suites.memblock.lsq.vlq.types import RobPtr


@pytest.mark.parametrize("memory", (1, 2, 7))
async def test_real_psq_special_finish_cannot_release_stalled_older_write(psq, memory):
    env = psq
    names = ("PSQ-DEQ.special_order",)
    env.begin(names)
    await env.cycle(enqueue=SqPtr.encode(2), addresses=(Address(True, 0, 6, 0x30000, 0xABC000, 3), Address()),
                    data=(Data(True, 0, 6, 0x8877665544332211), Data()))
    await env.cycle(addresses=(Address(),) * 2, data=(Data(),) * 2)
    for _ in range(12):
        await env.cycle(retired=SqPtr.encode(1))
        if env.observed[P.p_writeToSbuffer_req_0_valid]:
            break
    assert env.observed[P.p_writeToSbuffer_req_0_valid]
    await env.cycle(addresses=(Address(True, 1, 6, 0x40000, 0xDEF000, 3), Address()), data=(Data(True, 1, 6, 0x1111222233334444), Data()),
                    precommit_valid=True, precommit=SqPtr.encode(2), rob=RobPtr.encode(11))
    await env.cycle(addresses=(Address(),) * 2, data=(Data(),) * 2, attributes=(Attributes(nc=memory == 1, mmio=memory != 1, memory=memory < 4), Attributes()))
    for _ in range(12):
        await env.cycle()
        if env.observed[P.p_toUncacheBuffer_req_valid]:
            break
    assert env.observed[P.p_toUncacheBuffer_req_valid]
    await env.cycle(uncache_ready=True)
    if memory == 1:
        await env.cycle(uncache_ack_valid=True)
        await env.cycle(uncache_ack_valid=False)
    else:
        await env.cycle(uncache_response=True)
        await env.cycle(uncache_response=False, writeback_ready=True)
        assert env.pre_observed[P.p_writeBack_valid]
        await env.cycle(writeback_ready=False)
    evidence = {"nodeid": env.nodeid, "memory_type": memory, "tick": env.last_tick, "head_before": read_ptr(env.pre_observed),
                "head_after": read_ptr(env.observed), "older_write_still_valid": env.observed[P.p_writeToSbuffer_req_0_valid],
                "sbuffer_ready": list(env.controls.sbuffer_ready), "required_head": 0}
    Path(env.journal.name).with_name("special-order-check.json").write_text(json.dumps(evidence, indent=2) + "\n")
    assert read_ptr(env.observed) == 0, ("young NC/IO finish must not release an unconsumed old PSQ owner", evidence)
    # A fixed implementation must still complete the old request, not merely
    # hold the pointer forever; the full stage/UID suites retain drain checks.
    await env.cycle(sbuffer_ready=(True, True))
    await env.idle(6)
    assert read_ptr(env.observed) == 2
    env.finish(names)
