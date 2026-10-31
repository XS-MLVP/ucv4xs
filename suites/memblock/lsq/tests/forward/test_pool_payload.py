"""64 public slots, three query lanes and four full-width payload lifetimes."""

import hashlib
import json

from suites.memblock.lsq.legacy_pins import P
from suites.memblock.lsq.forward.types import Translation
from suites.memblock.lsq.raw.types import SqPtr
from suites.memblock.lsq.store_payload import add_digest, check_forward, payload


async def test_all_slots_full_width_high_low_payload_lifetimes(forward, tmp_path):
    env = forward
    lifetimes, all_uids, stream = [], [], hashlib.sha256()
    for generation in range(4):
        start = generation * 64
        bank = {slot: env.store(vaddr=va, page=pa // 4096, size=4, data=data)
                for slot in range(64) for va, pa, data in (payload(generation, slot),)}
        await env.cycle(dequeue=SqPtr.encode(start), upper=SqPtr.encode(start + 64), stores=env.bank(bank))
        uids = []
        for slot in range(64):
            expected = payload(generation, slot)
            query = env.query(vaddr=expected[0], sq=start + 64, size=4)
            change = await env.cycle(queries=(query,) * 3)
            accepted = change["accepted"]
            assert len(accepted) == 3
            uids.extend(job["uid"] for job in accepted)
            env.arm(("FWD-PAYLOAD.pool",), uids[-3:])
            await env.cycle(translations=(Translation(expected[1]),) * 3)
            for lane in range(3):
                check_forward(env.observed, P.io(f"query_{lane}_s2Resp_"), expected)
                add_digest(stream, [generation, slot, lane, *expected])
        await env.idle(3)
        assert set(uids) <= env.coverage.completed and len(uids) == 192
        lifetimes.append(dict(generation=generation, head_before=start, head_after=start + 64,
                              public_slots=list(range(64)), checked_three_lane_responses=192,
                              first_payload=payload(generation, 0), last_payload=payload(generation, 63)))
        all_uids.extend(uids)
    assert len(all_uids) == len(set(all_uids)) == len(env.coverage.completed) == 768
    assert not env.coverage.killed
    witness = dict(format="lsq-store-payload-pool-witness-v1", dut="forward_module", lifetimes=lifetimes,
                   distinct_uids=768, checked_three_lane_responses=768, completed_owners=768,
                   payload_and_consumption_SHA256=stream.hexdigest(),
                   scope="public Store bank inputs and actual three-lane valid S2 byte payloads; no persistent storage claimed for combinational bank inputs")
    (tmp_path / "store-payload-pool-witness.json").write_text(json.dumps(witness, indent=2) + "\n")
