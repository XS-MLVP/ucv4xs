"""Caller-owned, peer-valid bus histories, not RTL or snapshot mutations."""
import pytest

from suites.frontend.ifu.testbenches.ifu.transactions import ProducerFetchRequest
from suites.frontend.ifu.testbenches.ifu.transactions import Frame
from suites.frontend.ifu.testbenches.ifu.model.cenc import c_addi
from suites.frontend.ifu.testbenches.ifu.model.fetch import build_window
from suites.frontend.ifu.testbenches.ifu.model.isa import addi
from suites.frontend.ifu.testbenches.uncache_unit.transactions import BusReply

pytestmark = pytest.mark.feature('IFU-TOP-009')


def item(pc=0x60000, address=None, *, mmio=0, pbmt=1, ftq=(0, 1)):
    # A short predicted-taken block is legal even when prediction is wrong.
    return ProducerFetchRequest(build_window([(c_addi(8, 1), 1)], pc, taken0=1,
                                            pmp0=mmio, pbmt0=pbmt, ftq0=ftq),
                                (0x8000 | (pc & 0xfff)) if address is None else address)


@pytest.mark.parametrize('mmio,pbmt', [(0, 1), (0, 2), (1, 0), (1, 1), (1, 2)])
async def test_peer_valid_memory_types_complete_one_issued_instruction(ifu_agent, mmio, pbmt):
    result = await ifu_agent.read_uncached(item(mmio=mmio, pbmt=pbmt), BusReply(c_addi(10, 5)))
    assert result.bus.address == 0x8000 and result.bus.main_memory == 1 - mmio
    assert result.bus.noncacheable == int(pbmt == 1)
    assert result.beat.valid == result.beat.enq == 1 and result.redirect.can_train == 0
    assert ifu_agent.bus_fires == ifu_agent.beat_fires == ifu_agent.redirects == 1
    assert result.input_source == result.peer_source == 'producer'


@pytest.mark.parametrize('corrupt,denied,exception', [(0, 0, 0), (1, 0, 5), (1, 1, 3)])
async def test_bus_error_priority_and_full_byte_address_upper_bit(ifu_agent, corrupt, denied, exception):
    result = await ifu_agent.read_uncached(item(pc=0x60ffe, address=(1 << 48) - 2), BusReply(c_addi(10, 5), corrupt, denied))
    assert result.bus.address == (1 << 48) - 2
    assert result.beat.exception_type == exception and result.beat.exception_mask == 1


async def test_real_page_final_resend_and_noncontiguous_page_continuation(ifu_agent):
    word = addi(5, 6, 1)
    first = await ifu_agent.read_uncached(item(pc=0x60FFE, address=0x8FFE), BusReply(word & 0xffff, need_resend=1))
    assert first.resend == 1 and first.beat is None and first.redirect.target == 0x61000
    assert first.peer_source == 'producer' and ifu_agent.carry.low == word & 0xffff
    second = await ifu_agent.read_uncached(item(pc=0x61000, address=0x12345000, ftq=(0, 2)), BusReply(word >> 16))
    assert second.resend == 0 and second.beat.instrs[0] == word and second.beat.is_rvc[0] == 0
    assert second.redirect.target == 0x61002 and second.redirect.offset == 0
    assert ifu_agent.carry is None and ifu_agent.bus_fires == 2 and ifu_agent.beat_fires == 1


async def test_bus_backpressure_holds_request_without_counting_multiple_issues(ifu_agent):
    checked = await ifu_agent.cycle(Frame(request=item()))
    uid = checked.accepted_uid
    for _ in range(6):
        checked = await ifu_agent.cycle()
    assert checked.before.bus is not None and ifu_agent.bus_fires == 0
    first = checked.before.bus
    for _ in range(3):
        checked = await ifu_agent.cycle()
        assert checked.before.bus == first and checked.bus_fire_uid is None
    assert (await ifu_agent.cycle(Frame(uncache_ready=1))).bus_fire_uid == uid
    await ifu_agent.reply(uid, BusReply(c_addi(10, 5)))
    assert (await ifu_agent.collect(uid)).beat is not None and ifu_agent.bus_fires == 1


async def test_nonidempotent_read_waits_for_real_older_instruction_drain(ifu_agent):
    cached = ProducerFetchRequest(build_window([(c_addi(8, 1), 1)] * 32, 0x62000, ftq0=(0, 3)))
    await ifu_agent.fetch(cached)  # Explicit history makes isFirstInstr false.
    accepted = await ifu_agent.cycle(Frame(request=item(pc=0x62100, mmio=1, pbmt=0, ftq=(0, 4)),
        backend_empty=0, ibuffer_empty=0, uncache_ready=1))
    for _ in range(6):
        checked = await ifu_agent.cycle(Frame(backend_empty=0, ibuffer_empty=0, uncache_ready=1))
        assert checked.before.bus is None
    assert ifu_agent.bus_fires == 0
    uid = accepted.accepted_uid
    for _ in range(4):
        checked = await ifu_agent.cycle(Frame(uncache_ready=1))
        if checked.bus_fire_uid == uid:
            break
    assert checked.bus_fire_uid == uid
    await ifu_agent.reply(uid, BusReply(c_addi(10, 5)))
    assert (await ifu_agent.collect(uid)).beat.enq == 1


async def test_backend_flush_cancels_issued_work_and_new_read_has_a_new_uid(ifu_agent):
    old = await ifu_agent.send_uncached(item())
    await ifu_agent.cancel_pending('backend and peer coordinate flush of the old uncached generation')
    assert ifu_agent.records[-1].state == 'cancelled'
    late = await ifu_agent.reply(old, BusReply(c_addi(10, 5)))
    assert late.beat_uid is None and late.redirect_uid is None and ifu_agent.ignored_replies == 1
    new = await ifu_agent.read_uncached(item(pc=0x63000, ftq=(0, 5)), BusReply(c_addi(10, 5)))
    assert new.uid != old and ifu_agent.beat_fires == 1


@pytest.mark.feature('IFU-TOP-011')
async def test_cached_low_half_can_finish_through_the_uncached_peer(ifu_agent):
    word = addi(5, 6, 1)
    program = [(c_addi(8, 1), 1)] * 31 + [(word, 0)]
    first = ProducerFetchRequest(build_window(program, 0x64000, truncate=1, ftq0=(0, 6)))
    assert (await ifu_agent.fetch(first)).beat.enq == (1 << 31) - 1
    second = await ifu_agent.read_uncached(item(pc=0x64040, address=0x3040, ftq=(0, 7)), BusReply(word >> 16))
    assert second.beat.instrs[3] == word and second.beat.end_off[3] == 0
    assert second.beat.ftq[3] == (0, 7) and second.redirect.target == 0x64042
    assert ifu_agent.carry is None
