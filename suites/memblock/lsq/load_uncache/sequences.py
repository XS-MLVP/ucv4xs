"""Legal traffic construction, independent of the expected output calculation."""
from suites.memblock.lsq.uncache_entry.types import RobPtr


def red(rob, self_flush=False, valid=True):
    return {"io_redirect_valid": valid, "io_redirect_bits_robIdx_flag": rob.flag, "io_redirect_bits_robIdx_value": rob.value,
            "io_redirect_bits_robIdx_isFormer": rob.former, "io_redirect_bits_level": self_flush}


async def allocate_batch(env, requests, *, pending=RobPtr.encode(140)):
    await env.enqueue(requests, pending=pending)
    await env.cycle()
    return [tx["uid"] for tx in env.last_change["allocated"]]


async def fill(env, count=16, *, base=10):
    requests = [env.request(nc=True, rob=base + i, lq=(base + i) % 240, paddr=0x123400000000 + i * 0x1000, tag=i + 1) for i in range(count)]
    uids = []
    for offset in range(0, count, 3):
        batch = requests[offset:offset + 3]
        uids.extend(await allocate_batch(env, dict(enumerate(batch))))
    return requests, uids
