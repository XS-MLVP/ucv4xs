"""Independent real parent zero-write ownership at an actual WB transfer."""

import json
from pathlib import Path

import pytest

from suites.memblock.lsq.testbenches.psq.tests.helpers import observation
from suites.memblock.lsq.testbenches.psq.tests.helpers import sqptr
from suites.memblock.lsq.testbenches.psq.tests.helpers import word
from suites.memblock.lsq.testbenches.psq.transactions import Address
from suites.memblock.lsq.testbenches.psq.transactions import Data
from suites.memblock.lsq.testbenches.raw.transactions import SqPtr
from suites.memblock.lsq.testbenches.vlq.transactions import RobPtr


@pytest.mark.parametrize("old_queued", (False, True))
async def test_zero_wb_has_its_own_real_zero_sbuffer_transfer(psq, old_queued):
    env = psq
    names = ("PSQ-SPECIAL.zero_owner",) if old_queued else ("PSQ-SPECIAL.cbo",)
    env.begin(names)
    if old_queued:
        await env.cycle(enqueue=SqPtr.encode(2), addresses=(Address(True, 0, 6, 0x10000, 0xABC000, 3), Address()),
                        data=(Data(True, 0, 6, 0x1122334455667788), Data()))
        await env.cycle(addresses=(Address(), Address()), data=(Data(), Data()))
        for _ in range(12):
            await env.cycle(retired=SqPtr.encode(1))
            if env.response.sbuffer_word_0 is not None:
                break
        env.expect(observation(sbuffer_word_0=word(wline=0)), "older retired ordinary store is still queued, not consumed")
    slot = int(old_queued)
    zero_va, zero_pa = 0x20000, 0xDEF000
    await env.cycle(enqueue=SqPtr.encode(slot + 1), rob=RobPtr.encode(9), addresses=(Address(True, slot, 7, zero_va, zero_pa, 3), Address()),
                    data=(Data(True, slot, 7, (1 << 128) - 1), Data()), precommit_valid=True, precommit=SqPtr.encode(slot + 1))
    await env.cycle(addresses=(Address(), Address()), data=(Data(), Data()))
    await env.idle(6)
    fires = []
    wb = None
    for _ in range(20):
        await env.cycle(sbuffer_ready=(True, True), writeback_ready=True)
        pre = env.pre_response
        for lane in range(2):
            fired = pre.sbuffer_word_0 if lane == 0 else pre.sbuffer_word_1
            if fired is not None:
                fires.append({"tick": env.last_tick, "va": fired.vaddr, "pa": fired.addr,
                              "wline": fired.wline, "data": fired.data})
        if pre.writeback is not None:
            wb = {"tick": env.last_tick, "rob_value": pre.writeback.rob.value}
            break
    assert wb is not None and wb["rob_value"] == 9
    await env.idle(3)
    env.expect(observation(sq_deq_ptr=sqptr(slot + 1)), "actual zero WB also caused real SQ ownership release")
    zero_fires = [fire for fire in fires if fire["va"] == zero_va and fire["pa"] == zero_pa and fire["wline"] == 1 and fire["data"] == 0]
    release = env.response.sq_deq_ptr
    evidence = {"nodeid": env.nodeid, "old_queued": old_queued, "sbuffer_fires": fires, "actual_zero_wb_fire": wb,
                "zero_transfers_before_wb": len(zero_fires), "required_zero_transfers": 1,
                "actual_sq_release": {"tick": env.last_tick, "first": release.first,
                                      "second": release.second, "value": release.value}}
    Path(env.journal.name).with_name("zero-owner-check.json").write_text(json.dumps(evidence, indent=2) + "\n")
    assert len(zero_fires) == 1, ("CBO.zero completed at actual WB without its own real zero Sbuffer transfer", evidence)
    env.expect(observation(sq_deq_ptr=sqptr(slot + 1)), "zero owner completes exactly once after its own zero write")
    env.finish(names)
