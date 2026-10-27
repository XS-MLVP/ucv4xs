from lsqverify.forward.types import Query, Translation
from lsqverify.psq.types import Address, Attributes, Data
from lsqverify.raw.types import SqPtr
from lsqverify.vlq.types import RobPtr

from lsqverify.psq.checks import check_word, ptr_values, read_ptr


def source(uid, slot):
    size = uid % 5
    length = 1 << size
    offset = 0 if size == 4 else uid % (17 - length)
    va, pa = 0x100000 + uid * 4096 + offset, 0xB000000 + uid * 4096 + offset
    data = int.from_bytes(bytes((uid * 19 + byte * 17) % 256 for byte in range(16)), "little")
    # 16B is a continuous-vector chunk, not a nonexistent scalar store.q.
    op = (0x200 if size == 4 else 0) | size << 1
    return Address(True, slot, op, va, pa, size, unaligned=bool(offset)), Data(True, slot, op, data)


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
        env.expect({**ptr_values("io_toLoadQueue_stAddrReadySqPtr_", end), **ptr_values("io_toLoadQueue_stDataReadySqPtr_", end),
                    **ptr_values("io_sqDeqPtr_", base), "io_sbufferCtrl_req_forceWrite": 1}, "all 64 actual physical owners ready without retirement")
        for slot, (address, data) in enumerate(owners):
            query = Query(True, address.vaddr, SqPtr.encode(end), address.size)
            await env.cycle(queries=(query,) * 3)
            await env.cycle(queries=(Query(),) * 3, translations=(Translation(address.paddr),) * 3)
            expected = {}
            for lane in range(3):
                prefix = f"io_forward_{lane}_s2Resp_"
                expected.update({prefix + "valid": 1, prefix + "bits_forwardInvalid": 0, prefix + "bits_matchInvalid": 0,
                                 prefix + "bits_addrInvalid_valid": 0, prefix + "bits_dataInvalid_valid": 0})
                for byte in range(16):
                    offset = byte - address.vaddr % 16
                    active = 0 <= offset < 1 << address.size
                    expected[prefix + f"bits_forwardMask_{byte}"] = int(active)
                    if active:
                        expected[prefix + f"bits_forwardData_{byte}"] = data.data >> (8 * offset) & 255
            env.expect(expected, "all actual slots forward new-generation original bytes on all three load lanes")
        consumed = credits = quiet = 0
        for _ in range(100):
            await env.cycle(retired=SqPtr.encode(end), sbuffer_ready=(True, True))
            for lane in range(2):
                if env.pre_observed[f"io_writeToSbuffer_req_{lane}_valid"]:
                    address, data = owners[consumed]
                    mask = ((1 << (1 << address.size)) - 1) << (address.vaddr % 16)
                    check_word(env, lane, address.vaddr // 16 * 16, address.paddr // 16 * 16, mask,
                               (data.data << (8 * (address.vaddr % 16))) & ((1 << 128) - 1), before=True)
                    consumed += 1
            credits += env.pre_observed["io_sqDeq_bits"] if env.pre_observed["io_sqDeq_valid"] else 0
            quiet = quiet + 1 if read_ptr(env.observed) == end % 256 else 0
            if quiet == 4:
                break
        assert consumed == credits == 64 and quiet == 4
        env.expect({"io_empty": 1, "io_sbufferCtrl_req_forceWrite": 0}, "all 64 owners really completed before reusing their physical slots")
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
            pins = env.observed
            await env.cycle(sbuffer_ready=(True, True), cache_ready=bool(pins["io_toDCache_req_valid"]),
                            cache_response=bool(pins["io_toDCache_resp_ready"]), writeback_ready=bool(pins["io_writeBack_valid"]))
            pre = env.pre_observed
            if pre["io_toDCache_req_valid"] and env.controls.cache_ready:
                env.expect({"io_toDCache_req_bits_opcode": cbo, "io_toDCache_req_bits_address": pa}, "actual per-slot CBO operation request", before=True)
                cache_fires += 1
            if pre["io_writeToSbuffer_req_0_valid"]:
                assert cbo == 3
                check_word(env, 0, va, pa, 0xFF, 0, wline=1, before=True)
                sb_fires += 1
            if pre["io_writeBack_valid"] and env.controls.writeback_ready:
                env.expect({"io_writeBack_bits_exceptionVec_7": 0, "io_writeBack_bits_exceptionVec_19": 0,
                            "io_writeBack_bits_robIdx_value": position % 160, "io_writeBack_bits_robIdx_isFormer": position % 2},
                           "one real per-slot CBO WB fire with original ROB", before=True)
                wb_fires += 1
            credits += pre["io_sqDeq_bits"] if pre["io_sqDeq_valid"] else 0
            quiet = quiet + 1 if read_ptr(env.observed) == (position + 1) % 256 else 0
            if quiet == 4:
                break
        assert quiet == 4 and wb_fires == credits == 1
        assert (cache_fires, sb_fires) == ((0, 1) if cbo == 3 else (1, 0))
    env.finish(names)
