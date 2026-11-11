from dataclasses import replace

from suites.memblock.lsq.testbenches.forward.transactions import Query
from suites.memblock.lsq.testbenches.forward.transactions import Translation
from suites.memblock.lsq.testbenches.psq.env.actor import PsqActor
from suites.memblock.lsq.testbenches.psq.env.directed import consume_writes
from suites.memblock.lsq.testbenches.psq.env.directed import scalar_word
from suites.memblock.lsq.testbenches.psq.tests.helpers import forward
from suites.memblock.lsq.testbenches.psq.tests.helpers import observation
from suites.memblock.lsq.testbenches.psq.tests.helpers import sqptr
from suites.memblock.lsq.testbenches.psq.transactions import Address
from suites.memblock.lsq.testbenches.psq.transactions import Data
from suites.memblock.lsq.testbenches.raw.transactions import SqPtr


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
    env.expect(observation(addr_ready_ptr=sqptr(0), data_ready_ptr=sqptr(1),
                           addr_ready_mask=0b110, data_ready_mask=0b100),
               "independent address/data holes block only their own continuous prefixes")
    await env.cycle(addresses=(replace(owners[0][0], tlb_miss=True), Address()))
    await env.cycle(addresses=(Address(), Address()))
    await env.idle(3)
    env.expect(observation(addr_ready_ptr=sqptr(0), addr_ready_mask=0, addr_ready_clear_mask=1), "TLB miss cannot close the address hole")
    await env.cycle(addresses=(owners[0][0], Address()), data=(owners[1][1], Data()))
    await env.cycle(addresses=(Address(), Address()), data=(Data(), Data()))
    await consume_writes(env, [scalar_word(*owner) for owner in owners], 3, retired=SqPtr.encode(3))
    env.finish(names)


async def test_full_exception_blocks_head_cancel_and_new_uid_completes(psq_full):
    actor = PsqActor(psq_full)
    old = actor.add(exception=True)
    for _ in range(12):
        await actor.step(fair=True, precommit_valid=True, precommit=SqPtr.encode(1))
    assert not actor.completed and psq_full.response.sbuffer_word_0 is None
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
    psq_full.expect(observation(force_write=1, physical_upper=sqptr(64), sq_deq_ptr=sqptr(0)),
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
    env.expect(observation(forward=tuple(forward(valid=None, data_invalid=True) for _ in range(3))),
               "missing newest data blocks old-value success")
    env.expect(observation(forward=tuple(forward(valid=None, data_invalid_value=1) for _ in range(3))),
               "dependency points to actual youngest older SQ1")
    await env.cycle(data=(newer, Data()))
    await env.cycle(data=(Data(), Data()))
    await query_all(env, va, pa, 2)
    env.expect(observation(forward=tuple(forward(valid=1, forward_invalid=0, match_invalid=0, data_invalid=0,
                                                 data_byte_mask=0x00FF, forward_data=0x2222222222222222)
                                             for _ in range(3))),
               "newest data, never older data, is returned after actual STD arrival")
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
        if env.response.sbuffer_word_0 is not None:
            break
    await env.cycle(sbuffer_ready=(True, True), queries=(Query(True, address.vaddr, SqPtr.encode(1), 3),) * 3)
    assert env.pre_response.sbuffer_word_0 is not None
    await env.cycle(queries=(Query(),) * 3, translations=(Translation(address.paddr),) * 3)
    env.expect(observation(forward=tuple(forward() for _ in range(3))),
               "query accepted before release still has its staged response")
    await env.idle(4)
    env.expect(observation(sq_deq_ptr=sqptr(1)), "actual Sbuffer transfer has completed SQ release")
    await query_all(env, address.vaddr, address.paddr, 1)
    env.expect(observation(forward=tuple(forward(forward_mask=0) for _ in range(3))),
               "new queries after release cannot observe the old physical slot")
    env.finish(names)
