
from dataclasses import replace

from suites.memblock.lsq.legacy_pins import P
from suites.memblock.lsq.forward.types import Query, Translation
from suites.memblock.lsq.psq.actor import PsqActor
from suites.memblock.lsq.psq.checks import ptr_values
from suites.memblock.lsq.psq.directed import consume_writes, scalar_word
from suites.memblock.lsq.psq.types import Address, Attributes, Data
from suites.memblock.lsq.raw.types import SqPtr


async def query_all(env, va, pa, end, size=3):
    await env.cycle(queries=(Query(True, va, SqPtr.encode(end), size),) * 3)
    await env.cycle(queries=(Query(),) * 3, translations=(Translation(pa),) * 3)


async def test_full_ready_holes_tlb_retry_and_true_completion(psq_full):
    env = psq_full
    names = ("PSQ-READY.holes", "PSQ-STAGE.retry")
    env.begin(names)
    owners = [(Address(True, i, 6, 0x100000 + i * 4096, 0xA000000 + i * 4096, 3), Data(True, i, 6, 0x8877665544332200 + i)) for i in range(3)]
    await env.cycle(enqueue=SqPtr.encode(3), addresses=(owners[2][0], owners[1][0]), data=(owners[0][1], owners[2][1]))
    await env.cycle(addresses=(Address(), Address()), data=(Data(), Data()))
    await env.idle(3)
    env.expect({**ptr_values(P.p_toLoadQueue_stAddrReadySqPtr_, 0), **ptr_values(P.p_toLoadQueue_stDataReadySqPtr_, 1),
                P.p_toLoadQueue_stAddrReadyVec_1: 1, P.p_toLoadQueue_stAddrReadyVec_2: 1, P.p_toLoadQueue_stDataReadyVec_2: 1}, "independent address/data holes block only their own continuous prefixes")
    await env.cycle(addresses=(replace(owners[0][0], tlb_miss=True), Address()))
    await env.cycle(addresses=(Address(), Address()))
    await env.idle(3)
    env.expect({**ptr_values(P.p_toLoadQueue_stAddrReadySqPtr_, 0), P.p_toLoadQueue_stAddrReadyVec_0: 0}, "TLB miss cannot close the address hole")
    await env.cycle(addresses=(owners[0][0], Address()), data=(owners[1][1], Data()))
    await env.cycle(addresses=(Address(), Address()), data=(Data(), Data()))
    await consume_writes(env, [scalar_word(*owner) for owner in owners], 3, retired=SqPtr.encode(3))
    env.finish(names)


async def test_full_exception_blocks_head_cancel_and_new_uid_completes(psq_full):
    actor = PsqActor(psq_full)
    old = actor.add(exception=True)
    for _ in range(12):
        await actor.step(fair=True, precommit_valid=True, precommit=SqPtr.encode(1))
    assert not actor.completed and not psq_full.observed[P.p_writeToSbuffer_req_0_valid]
    assert await actor.cancel_suffix(0) == [old]
    new = actor.add(size=2)
    await actor.drain()
    assert old in actor.cancelled and old not in actor.completed
    actor.checked(("PSQ-PERMIT.exception", "PSQ-REUSE.cancelled", "PSQ-RECOVER.suffix"), [new])


async def test_full_virtual_128_allocations_respect_64_physical_issue_window(psq_full):
    actor = PsqActor(psq_full)
    uids = [actor.add(size=index % 5) for index in range(128)]
    for _ in range(4):
        await actor.step(issue=False, sbuffer_ready=(False, False))
    psq_full.expect({P.p_sbufferCtrl_req_forceWrite: 1, **ptr_values(P.p_physicalUpperSqIdx_, 64), **ptr_values(P.p_sqDeqPtr_, 0)},
                    "128 virtual owners can wait while only first 64 may issue")
    await actor.drain()
    assert len(actor.completed) == 128
    actor.checked(("PSQ-CAPACITY.virtual",), uids)


async def test_full_youngest_missing_data_then_newest_bytes_and_both_completions(psq_full):
    env = psq_full
    names = ("PSQ-FORWARD.wait", "PSQ-FORWARD.youngest")
    env.begin(names)
    va, pa = 0x300000, 0xB000000
    older, newer = Data(True, 0, 6, 0x1111111111111111), Data(True, 1, 6, 0x2222222222222222)
    a0, a1 = Address(True, 0, 6, va, pa, 3), Address(True, 1, 6, va, pa, 3)
    await env.cycle(enqueue=SqPtr.encode(2), addresses=(a0, a1), data=(older, Data()))
    await env.cycle(addresses=(Address(), Address()), data=(Data(), Data()))
    await env.idle(3)
    await query_all(env, va, pa, 2)
    env.expect({P.io(f"forward_{lane}_s2Resp_bits_dataInvalid_valid"): 1 for lane in range(3)}, "missing newest data blocks old-value success")
    env.expect({P.io(f"forward_{lane}_s2Resp_bits_dataInvalid_bits_value"): 1 for lane in range(3)}, "dependency points to actual youngest older SQ1")
    await env.cycle(data=(newer, Data()))
    await env.cycle(data=(Data(), Data()))
    await query_all(env, va, pa, 2)
    values = {}
    for lane in range(3):
        prefix = P.io(f"forward_{lane}_s2Resp_")
        values.update({prefix + "valid": 1, prefix + "bits_dataInvalid_valid": 0, prefix + "bits_matchInvalid": 0, prefix + "bits_forwardInvalid": 0})
        values.update({prefix + f"bits_forwardData_{byte}": 0x22 for byte in range(8)})
    env.expect(values, "newest data, never older data, is returned after actual STD arrival")
    await consume_writes(env, [scalar_word(a0, older), scalar_word(a1, newer)], 2, retired=SqPtr.encode(2))
    env.finish(names)


async def test_full_forward_at_actual_sbuffer_fire_and_after_dequeue_window(psq_full):
    env = psq_full
    names = ("PSQ-FORWARD.deq_window",)
    env.begin(names)
    address, data = Address(True, 0, 6, 0x400000, 0xC000000, 3), Data(True, 0, 6, 0x8877665544332211)
    await env.cycle(enqueue=SqPtr.encode(1), addresses=(address, Address()), data=(data, Data()))
    await env.cycle(addresses=(Address(), Address()), data=(Data(), Data()), retired=SqPtr.encode(1))
    for _ in range(12):
        await env.cycle()
        if env.observed[P.p_writeToSbuffer_req_0_valid]:
            break
    await env.cycle(sbuffer_ready=(True, True), queries=(Query(True, address.vaddr, SqPtr.encode(1), 3),) * 3)
    assert env.pre_observed[P.p_writeToSbuffer_req_0_valid]
    await env.cycle(queries=(Query(),) * 3, translations=(Translation(address.paddr),) * 3)
    env.expect({P.io(f"forward_{lane}_s2Resp_valid"): 1 for lane in range(3)}, "query accepted before release still has its staged response")
    await env.idle(4)
    env.expect(ptr_values(P.p_sqDeqPtr_, 1), "actual Sbuffer transfer has completed SQ release")
    await query_all(env, address.vaddr, address.paddr, 1)
    env.expect({P.io(f"forward_{lane}_s2Resp_bits_forwardMask_{byte}"): 0 for lane in range(3) for byte in range(16)}, "new queries after release cannot observe the old physical slot")
    env.finish(names)
