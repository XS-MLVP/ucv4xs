"""Pipeline overlap and valid-qualified side effects through the semantic API."""
import pytest

from suites.frontend.ifu.testbenches.ifu.transactions import FetchRequest
from suites.frontend.ifu.testbenches.ifu.transactions import Frame
from suites.frontend.ifu.testbenches.ifu.model.cenc import c_addi
from suites.frontend.ifu.testbenches.ifu.model.fetch import build_window
from suites.frontend.ifu.testbenches.ifu.model.isa import jal


def request(count, pc, index, **metadata):
    return FetchRequest(build_window([(c_addi(8 + lane, 1), 1) for lane in range(count)],
                                     pc, ftq0=(0, index), **metadata))


@pytest.mark.feature('IFU-TOP-004')
@pytest.mark.feature('IFU-TOP-006')
async def test_two_accepted_windows_keep_uid_payload_and_alignment_under_backpressure(ifu_agent):
    a = await ifu_agent.cycle(Frame(request=request(3, 0x60000, 1), ibuffer_ready=0))
    b = await ifu_agent.cycle(Frame(request=request(2, 0x60100, 2), ibuffer_ready=0))
    assert a.accepted_uid is not None and b.accepted_uid is not None and a.accepted_uid != b.accepted_uid
    for _ in range(4):
        checked = await ifu_agent.cycle(Frame(ibuffer_ready=0))
        assert checked.before.beat is not None and checked.beat_uid is None
    first = await ifu_agent.cycle()
    second = await ifu_agent.cycle()
    assert first.beat_uid == a.accepted_uid and second.beat_uid == b.accepted_uid
    assert ifu_agent.records[-1].shift == 3
    assert ifu_agent.beat_fires == 2


@pytest.mark.feature('IFU-TOP-008')
@pytest.mark.feature('IFU-TOP-006')
async def test_gpa_write_can_legally_repeat_while_one_enqueue_is_held(ifu_agent):
    item = request(2, 0x61000, 7, exc0=2, gp0=(1 << 56) - 2, vs0=1)
    accepted = await ifu_agent.cycle(Frame(request=item, ibuffer_ready=0))
    for _ in range(5):
        checked = await ifu_agent.cycle(Frame(ibuffer_ready=0))
        if checked.before.beat is not None:
            assert checked.before.gpa.address == (1 << 56) - 2
            assert checked.before.gpa.ftq_index == 7 and checked.before.gpa.for_vs == 1
    assert ifu_agent.gpa_writes >= 3 and ifu_agent.beat_fires == 0
    assert (await ifu_agent.cycle()).beat_uid == accepted.accepted_uid
    assert ifu_agent.beat_fires == 1


@pytest.mark.feature('IFU-TOP-007')
async def test_backend_flush_cancels_both_pipeline_stages_and_same_slot_fire(ifu_agent):
    a = await ifu_agent.cycle(Frame(request=request(3, 0x62000, 10), ibuffer_ready=0))
    b = await ifu_agent.cycle(Frame(request=request(2, 0x62100, 11), ibuffer_ready=0))
    flush = await ifu_agent.cycle(Frame(request=request(1, 0x62200, 12), backend_redirect=1, ibuffer_ready=0))
    assert flush.req_fire_uid is not None and flush.accepted_uid is None
    states = {record.uid: record.state for record in ifu_agent.records}
    assert states[a.accepted_uid] == states[b.accepted_uid] == 'cancelled'
    assert states[flush.req_fire_uid] == 'cancelled-on-fire'
    assert (await ifu_agent.fetch(request(2, 0x62300, 13))).beat is not None
    assert ifu_agent.records[-1].shift == 0 and ifu_agent.beat_fires == 1


@pytest.mark.feature('IFU-TOP-005')
@pytest.mark.feature('IFU-TOP-007')
async def test_prediction_redirect_cancels_younger_not_its_own_held_beat(ifu_agent):
    fault = FetchRequest(build_window([(jal(1, 0x40), 0)], 0x63000, ftq0=(0, 20)))
    older = await ifu_agent.cycle(Frame(request=fault, ibuffer_ready=0))
    younger = await ifu_agent.cycle(Frame(request=request(2, 0x63100, 21), ibuffer_ready=0))
    await ifu_agent.cycle(Frame(ibuffer_ready=0))
    redirect = await ifu_agent.cycle(Frame(ibuffer_ready=0))
    assert redirect.redirect_uid == older.accepted_uid and redirect.before.beat is not None
    states = {record.uid: record.state for record in ifu_agent.records}
    assert states[younger.accepted_uid] == 'cancelled' and states[older.accepted_uid] == 'pending'
    assert (await ifu_agent.cycle()).beat_uid == older.accepted_uid
    assert ifu_agent.beat_fires == ifu_agent.redirects == 1
