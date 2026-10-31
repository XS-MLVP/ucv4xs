"""Public bank age-prefix filtering, not a persistent Store lifecycle claim."""

import hashlib

from suites.memblock.lsq.legacy_pins import P
from suites.memblock.lsq.forward.types import Translation
from suites.memblock.lsq.raw.types import SqPtr
from suites.memblock.lsq.store_payload import add_digest
from suites.memblock.lsq.store_prefix import WINDOWS, check_byte, lifetime, producer, save_witness


async def test_nonfull_wrapped_exclusive_prefix_and_byte_offsets(forward, tmp_path):
    env, stream, lives, uids = forward, hashlib.sha256(), [], []
    for gen, (start, end) in enumerate(WINDOWS):
        bank = {position % 64: env.store(vaddr=va, page=pa // 4096, size=0, data=value)
                for position in range(start, end) for va, pa, value in (producer(gen, position),)}
        await env.cycle(dequeue=SqPtr.encode(start), upper=SqPtr.encode(end), stores=env.bank(bank))
        responses = 0
        for position in range(start, end):
            expected = producer(gen, position)
            q = env.query(vaddr=expected[0], sq=position + 1, size=0)
            change = await env.cycle(queries=(q,) * 3)
            current = [job["uid"] for job in change["accepted"]]
            assert len(current) == 3
            env.arm(("FWD-WINDOW.prefix_byte",), current)
            await env.cycle(translations=(Translation(expected[1]),) * 3)
            for lane in range(3):
                check_byte(env.observed, P.io(f"query_{lane}_s2Resp_"), expected)
                add_digest(stream, [gen, position, position + 1, lane, *expected])
                responses += 1
            uids.extend(current)
        await env.idle(3)
        assert set(uids) <= env.coverage.completed
        lives.append(lifetime(gen, responses, younger_alias_written_before_first_query=True))
    assert len(uids) == len(set(uids)) == len(env.coverage.completed) == 768 and not env.coverage.killed
    save_witness(tmp_path / "store-prefix-byte-witness.json", "forward_module", lives, stream,
                 completed_query_uids=768, scope="public bank, 768 valid S2 byte responses; no persistent Store/retirement claim at this combinational leaf")
