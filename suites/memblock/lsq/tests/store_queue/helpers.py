from suites.memblock.lsq.psq.types import Address, Data
from suites.memblock.lsq.raw.types import SqPtr
from suites.memblock.lsq.vlq.types import RobPtr
from suites.memblock.lsq.vsq.types import Dispatch


def requests(items, *, start=0):
    """lane -> (ROB, flows), caller-owned compact physical tail."""
    result, end = [Dispatch()] * 8, start
    for lane, (rob, flows) in sorted(items.items()):
        end += flows
        result[lane] = Dispatch(True, True, RobPtr.encode(rob) if isinstance(rob, int) else rob, flows, SqPtr.encode(end))
    return tuple(result)


def pair(item, lane):
    return tuple(item if i == lane else type(item)() for i in range(2))


async def write(env, address, data, *, lane=0, attributes=None):
    controls = {} if attributes is None else {"attributes": pair(attributes, lane)}
    await env.cycle(addresses=pair(address, lane), data=pair(data, 1 - lane))
    await env.cycle(addresses=(Address(), Address()), data=(Data(), Data()), **controls)


async def wait_valid(env, key, *, limit=30, **controls):
    for _ in range(limit):
        await env.cycle(**controls)
        if env.observed[key]:
            return
    raise AssertionError(("real StoreQueue did not produce required output", key))


async def finish_special(env, end):
    for _ in range(35):
        await env.cycle()
        if env.observed["io_sqEmpty"]:
            break
    from suites.memblock.lsq.psq.checks import ptr_values
    env.expect({"io_sqEmpty": 1, **ptr_values("io_sqDeqPtr_", end)}, "real physical completion feeds back and releases the original virtual owner")
    await env.idle(3)
