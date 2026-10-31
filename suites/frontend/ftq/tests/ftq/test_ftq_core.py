"""FTQ top: admission, pointer ownership, prefetch/fetch, redirect, commit."""

from __future__ import annotations

import pytest

from suites.frontend.ftq.ftq.transaction.types import BackendRedirect
from suites.frontend.ftq.ftq.transaction.types import IfuRedirect
from suites.frontend.ftq.ftq.transaction.types import Meta
from suites.frontend.ftq.ftq.transaction.types import Prediction
from suites.frontend.ftq.ftq.transaction.types import PredictionSpec
from suites.frontend.ftq.oracle import CallRet
from tests.ftq.support import allocate
from tests.ftq.support import branches
from tests.ftq.support import resolve

pytestmark = pytest.mark.feature("FTQ-TOP-001")

PC0 = 0x8000_1000
TARGET = 0x8000_3000


def assert_no_idle_outputs(agent) -> None:
    assert not agent.prefetch().valid
    assert not agent.fetch().valid
    assert not agent.backend_write().wen
    assert agent.training() is None
    assert agent.commit_event() is None
    assert agent.redirect_event() is None
    assert not agent.flush().to_ifu_redirect
    assert not agent.flush().redirect_flush


async def test_reset_initializes_all_queue_owners_and_idles_cleanly(ftq_agent):
    agent = ftq_agent
    await agent.reset()
    state = agent.pointers()
    assert (state.bpu.flag, state.bpu.value) == (0, 0)
    # FtqPtrVec initializes entry k to base+k in the same lap.
    assert [(owner.flag, owner.value) for owner in state.pf] == [(0, 0), (0, 1)]
    assert [(owner.flag, owner.value) for owner in state.fetch] == [(0, 0), (0, 1)]
    assert (state.commit.flag, state.commit.value) == (0, 0)
    assert (state.pnr.flag, state.pnr.value) == (0, 0)
    assert agent.prediction_ready()
    assert_no_idle_outputs(agent)
    for _ in range(4):
        await agent.step(1)
        assert_no_idle_outputs(agent)


@pytest.mark.feature("FTQ-TOP-002")
async def test_accepted_prediction_owns_one_entry_and_writes_backend_pc(ftq_agent):
    agent = ftq_agent
    await agent.reset()
    offer = await agent.offer(Prediction(PC0, taken=1, end_position=5))
    assert offer.ready and offer.wen
    assert (offer.index, offer.start_pc) == (0, PC0)

    await agent.step(1)
    await agent.complete_offer()
    await agent.step(1)

    assert agent.pointers().bpu.value == 1
    entry = agent.entry(0)
    assert (entry.start_pc, entry.taken, entry.end_position) == (PC0, 1, 5)
    assert not agent.backend_write().wen
    assert agent.prefetch().valid
    assert agent.fetch().valid


@pytest.mark.feature("FTQ-TOP-003")
async def test_prefetch_depth_stalls_prediction_admission_without_losing_state(ftq_agent):
    agent = ftq_agent
    await allocate(agent, 31)
    assert agent.pointers().bpu.value == 31
    assert agent.pointers().fetch[0].value == 0
    assert agent.prediction_ready()

    await allocate(agent, 1, base=0x8000_9000)
    assert agent.pointers().bpu.value == 32
    assert not agent.prediction_ready()

    await agent.consumers(prefetch=1, mainpipe=1)
    for _ in range(2):
        await agent.step(1)
    assert agent.pointers().fetch[0].value >= 1
    assert agent.prediction_ready()


@pytest.mark.feature("FTQ-TOP-004")
async def test_prefetch_request_describes_the_owned_entry_and_advances_once(ftq_agent):
    agent = ftq_agent
    specs = await allocate(agent, 2, with_meta=False)
    await agent.consumers(prefetch=1)
    request = agent.prefetch()

    assert request.valid
    assert request.start == specs[0].start_pc
    assert request.next_line == specs[0].start_pc + 0x20
    assert (request.index, request.index_flag) == (0, 0)
    assert request.set1 == (request.set0 + 1) & 0xFF
    assert not request.cross_line
    assert request.case == 0
    assert request.backend_exception == 0

    await agent.step(1)
    assert agent.pointers().pf[0].value == 1
    assert agent.prefetch().index == 1


@pytest.mark.feature("FTQ-TOP-006")
async def test_mainpipe_request_exposes_fetch_block_and_advances_once(ftq_agent):
    agent = ftq_agent
    specs = await allocate(agent, 2, with_meta=False)
    await agent.consumers(mainpipe=1)
    request = agent.fetch()

    assert request.valid
    assert request.addr0 == specs[0].start_pc
    assert request.addr1 == specs[0].start_pc + 0x20
    assert request.index == 0
    assert (request.taken, request.end_position) == (1, 3)
    assert not request.req1_valid

    await agent.step(1)
    assert agent.pointers().fetch[0].value == 1
    assert agent.fetch().index == 1


@pytest.mark.feature("FTQ-TOP-005")
@pytest.mark.feature("FTQ-TOP-009")
async def test_two_prefetch_requires_second_entry_past_pnr_and_same_page(ftq_agent):
    agent = ftq_agent
    # BPU s3 has retired entries 0..1; entries 2..3 remain speculative.
    await allocate(agent, 4, step=0x10, meta_limit=2)
    assert agent.pointers().pnr.value == 2

    await agent.consumers(prefetch=1)
    assert agent.prefetch().valid
    assert agent.prefetch().case == 1, "two entries in one cache line must be SameLine"
    await agent.step(1)
    assert agent.pointers().pf[0].value == 2

    # pnr=2 no longer covers the next pair (2,3), so the second request must
    # not be combined even though both are on the same page.
    assert agent.prefetch().case == 0
    await agent.step(1)
    assert agent.pointers().pf[0].value == 3


@pytest.mark.feature("FTQ-TOP-005")
async def test_two_prefetch_rejects_cross_page_pair(ftq_agent):
    agent = ftq_agent
    await allocate(agent, 2, base=0x8000_0FF0, step=0x20, meta_limit=2)
    assert agent.pointers().pnr.value == 2
    await agent.consumers(prefetch=1)
    assert agent.prefetch().valid
    assert agent.prefetch().case == 0
    await agent.step(1)
    assert agent.pointers().pf[0].value == 1


@pytest.mark.feature("FTQ-TOP-006")
@pytest.mark.feature("FTQ-TOP-009")
async def test_two_fetch_requires_pnr_page_size_and_real_two_fetch_response(ftq_agent):
    agent = ftq_agent
    await allocate(agent, 4, step=0x10, end_position=3, meta_limit=2)
    assert agent.pointers().pnr.value == 2

    await agent.consumers(mainpipe=1, real_two_fetch=1)
    request = agent.fetch()
    assert request.valid and request.req1_valid
    assert request.req1_index == 1
    await agent.step(1)
    assert agent.pointers().fetch[0].value == 2

    # The next pair has not passed pnr and must stay a single fetch.  The
    # consumer must also report realTwoFetchValid=0 for that single request.
    await agent.consumers(mainpipe=1, real_two_fetch=0)
    assert not agent.fetch().req1_valid
    await agent.step(1)
    assert agent.pointers().fetch[0].value == 3


@pytest.mark.feature("FTQ-TOP-006")
async def test_two_fetch_rejects_oversized_pair(ftq_agent):
    agent = ftq_agent
    await allocate(agent, 2, step=0x10, end_position=31, meta_limit=2)
    await agent.consumers(mainpipe=1, real_two_fetch=1)
    assert agent.fetch().valid
    assert not agent.fetch().req1_valid
    await agent.consumers(mainpipe=1, real_two_fetch=0)
    await agent.step(1)
    assert agent.pointers().fetch[0].value == 1


@pytest.mark.feature("FTQ-TOP-007")
async def test_s2_override_rewrites_owned_entry_and_rewinds_prefetch_fetch(ftq_agent):
    agent = ftq_agent
    await allocate(agent, 4, step=0x10, with_meta=False)
    await agent.consumers(prefetch=1, mainpipe=1)
    await agent.step(2)
    assert agent.pointers().pf[0].value >= 1
    assert agent.pointers().fetch[0].value >= 1

    new_pc = 0x8000_1200
    offer = await agent.offer(Prediction(
        new_pc, taken=0, end_position=7, s2_override=1, s2_ptr=1))
    flush = agent.flush()
    write = agent.backend_write()
    assert flush.s2_valid and flush.s2_value == 1
    assert write.wen and write.index == 1 and write.start_pc == new_pc

    await agent.consumers(prefetch=0, mainpipe=0)
    await agent.step(1)
    await agent.complete_offer()
    await agent.step(1)

    state = agent.pointers()
    assert state.bpu.value == 2
    entry = agent.entry(1)
    assert (entry.start_pc, entry.taken) == (new_pc, 0)
    assert state.pf[0].value == 1
    assert state.fetch[0].value == 1


@pytest.mark.feature("FTQ-TOP-008")
async def test_s3_override_has_priority_and_meta_advances_pnr(ftq_agent):
    agent = ftq_agent
    await allocate(agent, 4, step=0x10, with_meta=False)
    new_pc = 0x8000_1400
    offer = await agent.offer(Prediction(
        new_pc, taken=1, end_position=9, s2_override=1, s3_override=1,
        s2_ptr=1, s3_ptr=2))
    assert offer.index == 2, "s3 override must win over the s2 pointer"
    flush = agent.flush()
    write = agent.backend_write()
    assert flush.s3_valid and flush.s3_value == 2
    assert flush.ifu_s3_flush
    assert write.index == 2

    await agent.consumers(prefetch=0, mainpipe=0)
    await agent.step(1)
    await agent.complete_offer()
    await agent.step(1)
    assert agent.pointers().bpu.value == 3
    assert agent.entry(2).start_pc == new_pc

    await agent.write_meta(Meta(2))
    assert agent.pointers().pnr.value == 3


@pytest.mark.feature("FTQ-TOP-010")
async def test_backend_redirect_rewinds_all_owners_and_forwards_metadata(ftq_agent):
    agent = ftq_agent
    await allocate(agent, 4, with_meta=False)
    await agent.write_meta(Meta(
        2, fields=dict(redirectMeta_phr_phrPtr_value=0x155,
                       redirectMeta_commonHRMeta_ghr=0x1234)))
    target = 0x8000_5000
    event, flush = await agent.backend_redirect(BackendRedirect(
        2, pc=0x8000_2000, offset=0, target=target, branch_type=2,
        ras_action=1, level=1, debug_ctrl=1))

    assert flush.redirect_flush and flush.to_ifu_redirect
    assert event is not None
    assert event.cfi_pc == 0x8000_2000 >> 1
    assert event.target == target >> 1
    assert (event.taken, event.branch_type, event.ras_action) == (1, 2, 1)
    assert event.meta_phr == 0x155
    assert event.meta_ghr == 0x1234
    assert agent.redirect_topdown().backend_redirect
    assert agent.redirect_topdown().control_flow

    state = agent.pointers()
    assert state.bpu.value == 2
    assert state.pf[0].value == 2
    assert state.fetch[0].value == 2
    assert state.pnr.value == 2
    assert not agent.flush().redirect_flush


@pytest.mark.feature("FTQ-TOP-011")
async def test_ifu_return_redirect_uses_redirect_meta_return_address(ftq_agent):
    agent = ftq_agent
    await allocate(agent, 4, with_meta=False)
    await agent.write_meta(Meta(
        2, fields=dict(redirectMeta_ras_topRetAddr_addr=0x8000_5500)))
    event, flush = await agent.ifu_redirect(IfuRedirect(
        2, pc=0x8000_2000, offset=0, target=0x8000_6600,
        branch_type=3, ras_action=1, can_train=1))
    assert flush.redirect_flush
    assert event is not None
    assert event.target == 0x8000_5500
    assert (event.taken, event.branch_type) == (1, 3)
    assert agent.pointers().bpu.value == 3


@pytest.mark.feature("FTQ-TOP-011")
async def test_ifu_non_return_uses_explicit_target_and_can_suppress_training(ftq_agent):
    agent = ftq_agent
    await allocate(agent, 4, with_meta=False)
    target = 0x8000_7700
    event, _ = await agent.ifu_redirect(IfuRedirect(
        2, pc=0x8000_2000, offset=0, target=target,
        branch_type=1, ras_action=0, can_train=0))
    assert event is not None
    assert event.target == target >> 1
    assert agent.pointers().bpu.value == 3
    assert agent.training() is None


@pytest.mark.feature("FTQ-TOP-013")
async def test_commit_pointer_advances_once_per_retired_entry(ftq_agent):
    agent = ftq_agent
    await allocate(agent, 4, with_meta=False)
    assert agent.pointers().commit.value == 0

    await agent.commit(0)
    assert agent.pointers().commit.value == 1
    for _ in range(3):
        await agent.step(1)
        assert agent.pointers().commit.value == 1
    await agent.commit(1)
    assert agent.pointers().commit.value == 2
    await agent.step(2)
    assert agent.pointers().commit.value == 2


@pytest.mark.feature("FTQ-TOP-013")
async def test_commit_pointer_catches_up_to_a_repeated_retirement_pointer(ftq_agent):
    agent = ftq_agent
    await allocate(agent, 4, with_meta=False)
    await agent.commit(3)
    while agent.pointers().commit.value < 4:
        await agent.step(1)
    assert agent.pointers().commit.value == 4
    assert agent.pointers().bpu.value == 4


@pytest.mark.feature("FTQ-TOP-014")
async def test_call_return_commit_uses_stored_commit_meta(ftq_agent):
    agent = ftq_agent
    specs = [PredictionSpec(0x8000_1000 + index * 0x20) for index in range(6)]
    specs[5] = PredictionSpec(0x8000_10A0, meta=dict(
        commitMeta_ras_ssp=7,
        commitMeta_ras_tosw_flag=1,
        commitMeta_ras_tosw_value=9,
    ))
    await agent.allocate(specs)
    await agent.callret(0, CallRet(5, 2))
    event = agent.commit_event()
    assert event is not None
    assert (event.ras_action, event.meta_ssp, event.meta_tosw_flag,
            event.meta_tosw_value) == (2, 7, 1, 9)
    await agent.step(1)
    assert agent.commit_event() is None


@pytest.mark.feature("FTQ-TOP-015")
async def test_resolve_becomes_training_with_entry_meta_and_first_mispredict_mask(ftq_agent):
    agent = ftq_agent
    specs = [PredictionSpec(0x8000_4000 + index * 0x20) for index in range(5)]
    specs[4] = PredictionSpec(0x8000_4080, meta=dict(
        resolveMeta_phr_phrPtr_value=0x155,
        resolveMeta_commonHR_valid=1,
        resolveMeta_commonHR_ghr=0x1234,
    ))
    await agent.allocate(specs)
    await agent.consumers(train=0)
    await agent.resolve([
        resolve(4, pc=0x8000_4080, offset=2, mispredict=1),
        resolve(4, pc=0x8000_4080, offset=7, mispredict=0),
    ])
    for _ in range(6):
        if agent.training() is not None:
            break
        await agent.step(1)
    training = agent.training()
    assert training is not None
    assert training.start_pc == 0x8000_4080
    assert branches(agent) == [(2, 0x8000_3000)]
    assert training.meta_phr == 0x155
    assert training.meta_ghr == 0x1234
    agent.assert_training_mask()

    await agent.consumers(train=1)
    await agent.step(1)
    await agent.consumers(train=0)
    await agent.step(2)
    assert agent.training() is None


@pytest.mark.feature("FTQ-TOP-016")
async def test_train_cache_is_flushed_when_redirect_is_older_than_entry(ftq_agent):
    agent = ftq_agent
    await allocate(agent, 6, base=0x8000_5000, with_meta=False)
    await agent.resolve([resolve(5, pc=0x8000_50A0, offset=1)])
    for _ in range(6):
        if agent.training() is not None:
            break
        await agent.step(1)
    assert agent.training() is not None

    await agent.backend_redirect(BackendRedirect(
        2, pc=0x8000_2000, offset=1))
    assert agent.training() is None
