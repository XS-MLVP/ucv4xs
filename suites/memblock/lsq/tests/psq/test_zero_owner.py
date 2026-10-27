"""Independent real parent zero-write ownership at an actual WB transfer."""
import json
from pathlib import Path

import pytest

from lsqverify.psq.checks import ptr_values
from lsqverify.psq.types import Address, Data
from lsqverify.raw.types import SqPtr
from lsqverify.vlq.types import RobPtr


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
            if env.observed["io_writeToSbuffer_req_0_valid"]:
                break
        env.expect({"io_writeToSbuffer_req_0_valid": 1, "io_writeToSbuffer_req_0_bits_wline": 0}, "older retired ordinary store is still queued, not consumed")
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
        pre = env.pre_observed
        for lane in range(2):
            if pre[f"io_writeToSbuffer_req_{lane}_valid"]:
                fires.append({"tick": env.last_tick, "va": pre[f"io_writeToSbuffer_req_{lane}_bits_vaddr"],
                              "pa": pre[f"io_writeToSbuffer_req_{lane}_bits_addr"], "wline": pre[f"io_writeToSbuffer_req_{lane}_bits_wline"],
                              "data": pre[f"io_writeToSbuffer_req_{lane}_bits_data"]})
        if pre["io_writeBack_valid"]:
            wb = {"tick": env.last_tick, "rob_value": pre["io_writeBack_bits_robIdx_value"]}
            break
    assert wb is not None and wb["rob_value"] == 9
    await env.idle(3)
    env.expect(ptr_values("io_sqDeqPtr_", slot + 1), "actual zero WB also caused real SQ ownership release")
    zero_fires = [fire for fire in fires if fire["va"] == zero_va and fire["pa"] == zero_pa and fire["wline"] == 1 and fire["data"] == 0]
    evidence = {"nodeid": env.nodeid, "old_queued": old_queued, "sbuffer_fires": fires, "actual_zero_wb_fire": wb,
                "zero_transfers_before_wb": len(zero_fires), "required_zero_transfers": 1,
                "actual_sq_release": {"tick": env.last_tick, "first": env.observed["io_sqDeqPtr_first_flag"],
                                      "second": env.observed["io_sqDeqPtr_second_flag"], "value": env.observed["io_sqDeqPtr_value"]}}
    Path(env.journal.name).with_name("zero-owner-check.json").write_text(json.dumps(evidence, indent=2) + "\n")
    assert len(zero_fires) == 1, ("CBO.zero completed at actual WB without its own real zero Sbuffer transfer", evidence)
    env.expect(ptr_values("io_sqDeqPtr_", slot + 1), "zero owner completes exactly once after its own zero write")
    env.finish(names)
