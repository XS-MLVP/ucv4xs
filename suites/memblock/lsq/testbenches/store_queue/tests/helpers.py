from suites.memblock.lsq.testbenches.psq.transactions import Address
from suites.memblock.lsq.testbenches.psq.transactions import Data
from suites.memblock.lsq.testbenches.raw.transactions import SqPtr
from suites.memblock.lsq.testbenches.vlq.transactions import RobPtr
from suites.memblock.lsq.testbenches.vsq.transactions import Dispatch


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


def _channel(env, which):
    response = env.response
    return {
        "sbuffer_word_0": response.sbuffer_word_0 is not None,
        "sbuffer_word_1": response.sbuffer_word_1 is not None,
        "writeback": response.writeback is not None,
        "cache_request": response.cache_request is not None,
        "uncache_request": response.uncache_request is not None,
    }[which]


async def wait_valid(env, which, *, limit=30, **controls):
    for _ in range(limit):
        await env.cycle(**controls)
        if _channel(env, which):
            return
    raise AssertionError(("real StoreQueue did not produce required output", which))


async def finish_special(env, end):
    for _ in range(35):
        await env.cycle()
        if env.response.empty:
            break
    env.expect(observation(empty=1, sq_deq_ptr=sqptr(end)),
               "real physical completion feeds back and releases the original virtual owner")
    await env.idle(3)


# --- Typed observation constructors for functional tests ---
from suites.memblock.lsq.testbenches.shared.transactions import CacheRequest
from suites.memblock.lsq.testbenches.shared.transactions import ExceptionInfo
from suites.memblock.lsq.testbenches.shared.transactions import ForwardExpectation
from suites.memblock.lsq.testbenches.shared.transactions import RobIdentity
from suites.memblock.lsq.testbenches.shared.transactions import SbufferWord
from suites.memblock.lsq.testbenches.shared.transactions import UncacheRequest
from suites.memblock.lsq.testbenches.shared.transactions import Writeback
from suites.memblock.lsq.testbenches.store_queue.transactions import Observation


def observation(**fields):
    return Observation(**fields)


def word(*, addr=None, vaddr=None, mask=None, data=None, wline=None, valid=1):
    return SbufferWord(valid=valid, addr=addr, vaddr=vaddr, mask=mask, data=data, wline=wline)


def forward(*, valid=1, forward_mask=None, forward_data=None, data_byte_mask=None, data_invalid=None,
            data_invalid_value=None, match_invalid=None, forward_invalid=None,
            addr_invalid=None):
    return ForwardExpectation(valid=valid, forward_invalid=forward_invalid, match_invalid=match_invalid,
                              addr_invalid=addr_invalid, data_invalid=data_invalid,
                              data_invalid_value=data_invalid_value, forward_mask=forward_mask,
                              forward_data=forward_data, data_byte_mask=data_byte_mask)


def rob(value=None, flag=None, former=None):
    return RobIdentity(value, flag, former)


def writeback(*, rob_identity=None, access_fault=None, bus_error=None, mmio=None, ncio=None, valid=1):
    return Writeback(rob_identity, access_fault, bus_error, mmio, ncio, valid)


def cache(address=None, opcode=None, *, valid=1):
    return CacheRequest(address, opcode, valid)


def uncache(*, addr=None, vaddr=None, data=None, mask=None, ident=None, nc=None, memory_backed=None, rob_identity=None, valid=1):
    return UncacheRequest(addr, vaddr, data, mask, ident, nc, memory_backed, rob_identity, valid)


def exception(*, vaddr=None, hyper=None, access_fault=None, bus_error=None, rob_identity=None, valid=1):
    return ExceptionInfo(vaddr, hyper, access_fault, bus_error, rob_identity, valid)


def sqptr(position):
    return SqPtr.encode(position)


def check_word(env, lane, va, pa, mask, data, *, wline=0, before=False):
    byte_mask = sum(255 << (8 * byte) for byte in range(16) if mask >> byte & 1)
    env.expect_sbuffer_word(lane, word(addr=pa, vaddr=va, mask=mask, data=data, wline=wline),
                            "real StoreQueue source bytes at Sbuffer", data_mask=byte_mask, before=before)
