from suites.memblock.lsq.testbenches.forward.transactions import Query
from suites.memblock.lsq.testbenches.forward.transactions import Translation
from suites.memblock.lsq.testbenches.psq.tests.helpers import cache
from suites.memblock.lsq.testbenches.psq.tests.helpers import forward
from suites.memblock.lsq.testbenches.psq.tests.helpers import observation
from suites.memblock.lsq.testbenches.psq.tests.helpers import rob
from suites.memblock.lsq.testbenches.psq.tests.helpers import sqptr
from suites.memblock.lsq.testbenches.psq.tests.helpers import word
from suites.memblock.lsq.testbenches.psq.tests.helpers import writeback
from suites.memblock.lsq.testbenches.psq.transactions import Address
from suites.memblock.lsq.testbenches.psq.transactions import Data
from suites.memblock.lsq.testbenches.raw.transactions import SqPtr
from suites.memblock.lsq.testbenches.vlq.transactions import RobPtr


def source(uid, slot):
    size = uid % 5
    length = 1 << size
    offset = 0 if size == 4 else uid % (17 - length)
    va, pa = 0x100000 + uid * 4096 + offset, 0xB000000 + uid * 4096 + offset
    data = int.from_bytes(bytes((uid * 19 + byte * 17) % 256 for byte in range(16)), "little")
    # 16B is a continuous-vector chunk, not a nonexistent scalar store.q.
    op = (0x200 if size == 4 else 0) | size << 1
    return Address(True, slot, op, va, pa, size, unaligned=bool(offset)), Data(True, slot, op, data)


def scalar_word(address, data):
    mask = ((1 << (1 << address.size)) - 1) << (address.vaddr % 16)
    return word(addr=address.paddr // 16 * 16, vaddr=address.vaddr // 16 * 16, mask=mask,
                data=(data.data << (8 * (address.vaddr % 16))) & ((1 << 128) - 1), wline=0)


async def test_all_physical_slots_two_input_lanes_four_generations_complete(psq):
    env = psq
    names = ("PSQ-WRITE.slots", "PSQ-REUSE.completed", "PSQ-READY.upper", "PSQ-BYTE.sizes", "PSQ-CAPACITY.force")
    env.begin(names)
    for generation in range(4):
        base, end = generation * 64, generation * 64 + 64
        owners = [source(base + slot, slot) for slot in range(64)]
        for slot in range(0, 64, 2):
            pair = (owners[slot], owners[slot + 1]) if generation % 2 == 0 else (owners[slot + 1], owners[slot])
            await env.cycle(enqueue=SqPtr.encode(end), addresses=tuple(item[0] for item in pair), data=tuple(item[1] for item in pair),
                            retired=SqPtr.encode(base), sbuffer_ready=(False, False))
        await env.cycle(addresses=(Address(), Address()), data=(Data(), Data()))
        await env.idle(4)
        env.expect(observation(addr_ready_ptr=sqptr(end), data_ready_ptr=sqptr(end),
                               sq_deq_ptr=sqptr(base), force_write=1),
                   "all 64 actual physical owners ready without retirement")
        for slot, (address, data) in enumerate(owners):
            query = Query(True, address.vaddr, SqPtr.encode(end), address.size)
            await env.cycle(queries=(query,) * 3)
            await env.cycle(queries=(Query(),) * 3, translations=(Translation(address.paddr),) * 3)
            expected = []
            for lane in range(3):
                forwarded = 0
                for byte in range(16):
                    offset = byte - address.vaddr % 16
                    if 0 <= offset < 1 << address.size:
                        forwarded |= (data.data >> (8 * offset) & 0xFF) << (8 * byte)
                expected.append(forward(valid=1, forward_invalid=0, match_invalid=0, addr_invalid=0,
                                        data_invalid=0,
                                        forward_mask=sum(1 << byte for byte in range(16) if 0 <= byte - address.vaddr % 16 < 1 << address.size),
                                        forward_data=forwarded))
            env.expect(observation(forward=tuple(expected)),
                       "all actual slots forward new-generation original bytes on all three load lanes")
        consumed = credits = quiet = 0
        for _ in range(100):
            await env.cycle(retired=SqPtr.encode(end), sbuffer_ready=(True, True))
            for lane in range(2):
                fired = env.pre_response.sbuffer_word_0 if lane == 0 else env.pre_response.sbuffer_word_1
                if fired is not None:
                    address, data = owners[consumed]
                    expected_word = scalar_word(address, data)
                    env.expect_sbuffer_word(lane, expected_word,
                                            "real PSQ source bytes and control at Sbuffer", before=True,
                                            data_mask=sum(255 << (8 * byte) for byte in range(16) if expected_word.mask >> byte & 1))
                    consumed += 1
            credits += env.pre_response.dequeue_count if env.pre_response.dequeue_valid else 0
            quiet = quiet + 1 if env.deq_position == end % 256 else 0
            if quiet == 4:
                break
        assert consumed == credits == 64 and quiet == 4, (consumed, credits, quiet, env.last_tick)
        env.expect(observation(empty=1, force_write=0), "all 64 owners really completed before reusing their physical slots")
    env.finish(names)


async def test_cbo_all_slots_both_input_lanes_with_real_zero_cache_and_wb(psq):
    env = psq
    names = ("PSQ-SPECIAL.cbo",)
    env.begin(names)
    for position in range(128):
        slot, lane, cbo = position % 64, position // 64, position % 4
        op = cbo * 2 + 1
        va, pa = 0x400000 + position * 4096, 0xD000000 + position * 4096
        address, data = Address(True, slot, op, va, pa, 3), Data(True, slot, op, (1 << 128) - 1)
        await env.cycle(enqueue=SqPtr.encode(position + 1), retired=SqPtr.encode(position), rob=RobPtr.encode(position, former=bool(position % 2)),
                        addresses=tuple(address if index == lane else Address() for index in range(2)),
                        data=tuple(data if index == lane else Data() for index in range(2)),
                        cache_ready=False, cache_response=False, writeback_ready=False, sbuffer_ready=(False, False))
        await env.cycle(addresses=(Address(), Address()), data=(Data(), Data()), precommit_valid=True, precommit=SqPtr.encode(position + 1))
        cache_fires = sb_fires = wb_fires = credits = quiet = 0
        for _ in range(40):
            stats = env.response
            await env.cycle(sbuffer_ready=(True, True), cache_ready=stats.cache_request is not None,
                            cache_response=bool(stats.cache_response_ready), writeback_ready=stats.writeback is not None)
            pre = env.pre_response
            if pre.cache_request is not None and env.controls.cache_ready:
                env.expect(observation(cache_request=cache(address=pa, opcode=cbo, valid=None)),
                           "actual per-slot CBO operation request", before=True)
                cache_fires += 1
            if pre.sbuffer_word_0 is not None:
                assert cbo == 3
                env.expect_sbuffer_word(0, word(addr=pa, vaddr=va, mask=0xFF, data=0, wline=1),
                                        "real zero transfer", data_mask=(1 << 64) - 1, before=True)
                sb_fires += 1
            if pre.writeback is not None and env.controls.writeback_ready:
                env.expect(observation(writeback=writeback(
                    access_fault=0, bus_error=0, rob_identity=rob(position % 160, None, position % 2), valid=None)),
                    "one real per-slot CBO WB fire with original ROB", before=True)
                wb_fires += 1
            credits += pre.dequeue_count if pre.dequeue_valid else 0
            quiet = quiet + 1 if env.deq_position == (position + 1) % 256 else 0
            if quiet == 4:
                break
        assert quiet == 4 and wb_fires == credits == 1
        assert (cache_fires, sb_fires) == ((0, 1) if cbo == 3 else (1, 0))
    env.finish(names)
