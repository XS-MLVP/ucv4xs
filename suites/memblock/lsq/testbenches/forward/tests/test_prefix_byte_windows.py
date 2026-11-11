"""Public bank age-prefix filtering, not a persistent Store lifecycle claim."""

import hashlib

from suites.memblock.lsq.testbenches.forward.transactions import Translation
from suites.memblock.lsq.testbenches.raw.transactions import SqPtr
from suites.memblock.lsq.testbenches.store_queue.model.store_payload import add_digest
from suites.memblock.lsq.testbenches.store_queue.model.store_prefix import WINDOWS
from suites.memblock.lsq.testbenches.store_queue.model.store_prefix import check_byte_response
from suites.memblock.lsq.testbenches.store_queue.model.store_prefix import lifetime
from suites.memblock.lsq.testbenches.store_queue.model.store_prefix import producer
from suites.memblock.lsq.testbenches.store_queue.model.store_prefix import save_witness


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
                check_byte_response(env.response.responses[lane], expected)
                if lane == 0:
                    # The original check_byte rejected an expected page-offset
                    # mismatch before comparing payload; keep that input-domain
                    # control on the typed counterpart without touching the
                    # producer or the reference answer.
                    try:
                        check_byte_response(env.response.responses[lane],
                                            (expected[0], expected[1] + 1, expected[2]))
                    except AssertionError:
                        pass
                    else:
                        raise AssertionError("misaligned expected page offset must be rejected")
                add_digest(stream, [gen, position, position + 1, lane, *expected])
                responses += 1
            uids.extend(current)
        await env.idle(3)
        assert set(uids) <= env.coverage.completed
        lives.append(lifetime(gen, responses, younger_alias_written_before_first_query=True))
    assert len(uids) == len(set(uids)) == len(env.coverage.completed) == 768 and not env.coverage.killed
    save_witness(tmp_path / "store-prefix-byte-witness.json", "forward_module", lives, stream,
                 completed_query_uids=768, scope="public bank, 768 valid S2 byte responses; no persistent Store/retirement claim at this combinational leaf")
