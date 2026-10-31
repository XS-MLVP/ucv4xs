"""FTQ top: wrap, exception tagging, arbitration, pressure, and meta breadth."""

from __future__ import annotations

import pytest

from suites.frontend.ftq.ftq.transaction.types import BackendRedirect
from suites.frontend.ftq.ftq.transaction.types import IfuRedirect
from suites.frontend.ftq.ftq.transaction.types import Prediction
from suites.frontend.ftq.ftq.transaction.types import PredictionSpec
from suites.frontend.ftq.oracle import CallRet
from tests.ftq.support import allocate
from tests.ftq.support import resolve

PC0 = 0x8000_1000


@pytest.mark.feature("FTQ-TOP-003")
@pytest.mark.feature("FTQ-TOP-018")
async def test_full_ftq_stall_topdown_reason_and_commit_release(ftq_agent):
    agent = ftq_agent
    await allocate(agent, 64, base=PC0, step=0x20, consume=True)

    assert agent.pointers().bpu.flag == 1
    assert agent.pointers().bpu.value == 0
    assert agent.pointers().commit.value == 0
    assert not agent.prediction_ready()
    await agent.step(1)
    assert agent.topdown().reasons[9]

    # A single retirement makes room for exactly one more entry.
    await agent.commit(63)
    assert agent.pointers().commit.value == 2
    assert agent.prediction_ready()

    await allocate(agent, 1, base=0x8000_9000, step=0x20,
                   consume=True, with_meta=False)
    assert agent.pointers().bpu.flag == 1
    assert agent.pointers().bpu.value == 1
    assert agent.entry(0).start_pc == 0x8000_9000


@pytest.mark.feature("FTQ-TOP-012")
async def test_backend_exception_tags_prefetch_and_fetch_until_three_blocks_pass(ftq_agent):
    agent = ftq_agent
    await allocate(agent, 6, step=0x20, with_meta=False)
    await agent.backend_redirect(BackendRedirect(
        1, pc=0x8000_1100, offset=0, level=1, ipf=1))
    assert agent.pointers().bpu.value == 1

    await allocate(agent, 4, base=0x8000_1200, step=0x20, with_meta=False)
    await agent.consumers(prefetch=0, mainpipe=0)
    prefetch = agent.prefetch()
    fetch = agent.fetch()
    assert prefetch.index == 1 and prefetch.backend_exception == 1
    assert fetch.index == 1 and fetch.backend_exception

    await agent.consumers(mainpipe=1)
    for _ in range(3):
        await agent.step(1)
    await agent.consumers(prefetch=1)
    for _ in range(3):
        await agent.step(1)
    assert agent.prefetch().index == 4
    assert agent.prefetch().backend_exception == 0


@pytest.mark.feature("FTQ-TOP-012")
async def test_satp_flush_tags_fetch_without_inventing_an_exception(ftq_agent):
    agent = ftq_agent
    await allocate(agent, 4, step=0x20, with_meta=False)
    await agent.backend_redirect(BackendRedirect(
        1, pc=0x8000_1100, offset=0, level=1, satp_flush=1))
    await allocate(agent, 4, base=0x8000_1200, step=0x20, with_meta=False)
    await agent.consumers(prefetch=0, mainpipe=0)
    assert agent.prefetch().backend_exception == 0
    assert agent.fetch().satp_flush
    assert not agent.fetch().backend_exception


@pytest.mark.feature("FTQ-TOP-012")
async def test_guest_page_fault_maps_to_gpf(ftq_agent):
    agent = ftq_agent
    await allocate(agent, 6, step=0x20, with_meta=False)
    await agent.backend_redirect(BackendRedirect(
        2, pc=0x8000_2200, offset=2, level=1, igpf=1))
    assert agent.pointers().bpu.value == 3
    await allocate(agent, 4, base=0x8000_3000, step=0x20, with_meta=False)
    await agent.consumers(prefetch=0, mainpipe=0)
    assert agent.prefetch().index == 3
    assert agent.prefetch().backend_exception == 2
    assert agent.fetch().backend_exception


@pytest.mark.feature("FTQ-TOP-012")
async def test_access_fault_maps_to_af(ftq_agent):
    agent = ftq_agent
    await allocate(agent, 6, step=0x20, with_meta=False)
    await agent.backend_redirect(BackendRedirect(
        1, pc=0x8000_1200, offset=0, level=1, iaf=1))
    assert agent.pointers().bpu.value == 1
    await allocate(agent, 4, base=0x8000_2000, step=0x20, with_meta=False)
    await agent.consumers(prefetch=0, mainpipe=0)
    assert agent.prefetch().index == 1
    assert agent.prefetch().backend_exception == 3
    assert agent.fetch().backend_exception


@pytest.mark.feature("FTQ-TOP-010")
async def test_ftq_idx_ahead_match_removes_redirect_delay(ftq_agent):
    agent = ftq_agent
    await allocate(agent, 4, step=0x20, with_meta=False)
    await agent.ahead_set(2)
    await agent.ahead_clear()
    event, flush = await agent.drive_backend_redirect(BackendRedirect(
        2, pc=0x8000_2000, offset=0, level=1))
    assert event is not None, "a matched ahead index must redirect immediately"
    assert flush.redirect_flush
    await agent.finish_backend_redirect()
    assert agent.pointers().bpu.value == 2


@pytest.mark.feature("FTQ-TOP-010")
async def test_ftq_idx_ahead_mismatch_keeps_registered_redirect(ftq_agent):
    agent = ftq_agent
    await allocate(agent, 4, step=0x20, with_meta=False)
    await agent.ahead_set(3)
    await agent.ahead_clear()

    event, _ = await agent.drive_backend_redirect(BackendRedirect(
        2, pc=0x8000_2000, offset=0, level=1))
    assert event is None, "a mismatched ahead index must still delay the redirect"
    await agent.step(1)
    assert agent.redirect_event() is not None
    await agent.finish_backend_redirect()
    assert agent.pointers().bpu.value == 2


@pytest.mark.feature("FTQ-TOP-010")
async def test_backend_redirect_has_priority_over_ifu_redirect(ftq_agent):
    agent = ftq_agent
    await allocate(agent, 4, step=0x20, with_meta=False)
    backend_target = 0x8000_5000
    # Both source channels are idle except the backend redirect; the IFU
    # channel must not override its priority.
    await agent.drive_backend_redirect(BackendRedirect(
        2, pc=0x8000_2000, offset=0, level=1, target=backend_target))
    await agent.step(1)
    event = agent.redirect_event()
    assert event is not None
    assert event.target == backend_target >> 1
    await agent.release_backend_redirect()
    await agent.step(2)
    assert not agent.flush().redirect_flush


@pytest.mark.feature("FTQ-TOP-003")
@pytest.mark.feature("FTQ-TOP-018")
async def test_train_backpressure_ages_into_update_bubble(ftq_agent):
    agent = ftq_agent
    await allocate(agent, 3, base=0x8000_3000)
    await agent.resolve([resolve(2, pc=0x8000_3040, offset=1)])
    for _ in range(6):
        if agent.training() is not None:
            break
        await agent.step(1)
    assert agent.training() is not None

    # BpTrainStallLimit=8.  The counter is deliberately independent of the
    # queue-distance gates, so the ninth stalled train closes admission.
    for _ in range(8):
        assert agent.prediction_ready()
        await agent.step(1)
    assert not agent.prediction_ready()
    await agent.step(1)
    assert agent.topdown().reasons[2]

    await agent.consumers(train=1)
    await agent.step(1)
    await agent.consumers(train=0)
    await agent.step(2)
    assert agent.prediction_ready()


@pytest.mark.feature("FTQ-TOP-017")
async def test_high_index_meta_is_retained_for_redirect_train_and_commit(ftq_agent):
    agent = ftq_agent
    index = 40
    specs = [PredictionSpec(0x8000_4000 + offset * 0x20)
             for offset in range(index + 1)]
    specs[index] = PredictionSpec(0x8000_4000 + index * 0x20, meta=dict(
        redirectMeta_phr_phrPtr_value=0x2AA,
        redirectMeta_commonHRMeta_ghr=0xABCD,
        redirectMeta_ras_topRetAddr_addr=0x8000_7000,
        resolveMeta_phr_phrPtr_value=0x155,
        resolveMeta_commonHR_valid=1,
        resolveMeta_commonHR_ghr=0x1234,
        commitMeta_ras_ssp=3,
        commitMeta_ras_tosw_flag=1,
        commitMeta_ras_tosw_value=17,
    ))
    await agent.allocate(specs, consume=True)
    assert agent.meta_redirect(index, "phr_phrPtr_value") == 0x2AA
    assert agent.meta_redirect(index, "commonHRMeta_ghr") == 0xABCD
    assert agent.meta_redirect(index, "ras_topRetAddr_addr") == 0x8000_7000

    event, _ = await agent.backend_redirect(BackendRedirect(
        index, pc=0x8000_4500, offset=0, level=1))
    assert event is not None
    assert event.meta_phr == 0x2AA
    assert event.meta_ghr == 0xABCD

    await agent.resolve([resolve(index, pc=0x8000_4500, offset=3)])
    for _ in range(6):
        if agent.training() is not None:
            break
        await agent.step(1)
    training = agent.training()
    assert training is not None
    assert training.meta_phr == 0x155
    assert training.meta_ghr == 0x1234
    await agent.consumers(train=1)
    await agent.step(1)
    await agent.consumers(train=0)

    await agent.callret(0, CallRet(index, 1))
    event = agent.commit_event()
    assert event is not None
    assert (event.meta_ssp, event.meta_tosw_value) == (3, 17)


@pytest.mark.feature("FTQ-TOP-005")
@pytest.mark.parametrize("case,expected,advance", [
    ("same_line", 1, 2),
    ("overlap1", 2, 2),
    ("overlap2", 4, 2),
    ("interleave", 8, 2),
    ("conflict_cross_page", 0, 1),
])
async def test_two_prefetch_case_matrix(ftq_agent, case, expected, advance):
    agent = ftq_agent
    specs = {
        "same_line": ((0x8000_0000, 3, 0), (0x8000_0010, 3, 0)),
        "overlap1": ((0x8000_0010, 31, 1), (0x8000_0020, 3, 0)),
        "overlap2": ((0x8000_0060, 3, 1), (0x8000_0050, 31, 1)),
        "interleave": ((0x8000_0000, 3, 0), (0x8000_0020, 3, 0)),
        "conflict_cross_page": ((0x8000_2FE0, 3, 0), (0x8000_3000, 3, 0)),
    }[case]
    entries = [PredictionSpec(pc, taken=taken, end_position=end)
               for pc, end, taken in specs]
    entries += [PredictionSpec(0x8000_0100), PredictionSpec(0x8000_0120)]
    await agent.allocate(entries, meta_limit=2)
    await agent.consumers(prefetch=1)
    assert agent.prefetch().valid
    assert agent.prefetch().case == expected
    await agent.step(1)
    assert agent.pointers().pf[0].value == advance


@pytest.mark.feature("FTQ-TOP-006")
async def test_two_fetch_rejects_cross_page_pair(ftq_agent):
    agent = ftq_agent
    await allocate(agent, 2, base=0x8000_0FE0, step=0x20, meta_limit=2)
    assert agent.pointers().pnr.value == 2
    await agent.consumers(mainpipe=1)
    assert agent.fetch().valid
    assert not agent.fetch().req1_valid
    await agent.step(1)
    assert agent.pointers().fetch[0].value == 1


@pytest.mark.feature("FTQ-TOP-007")
async def test_redirect_cycle_suppresses_prediction_side_effects(ftq_agent):
    agent = ftq_agent
    await allocate(agent, 4, base=0x8000_1000, step=0x20, with_meta=False)
    original = agent.entry(2).start_pc

    await agent.offer(Prediction(0x8000_9000))
    await agent.drive_backend_redirect(BackendRedirect(
        2, pc=0x8000_1100, offset=0, level=1))
    await agent.step(1)
    assert agent.pointers().bpu.value == 5

    # The registered redirect now owns the pointers; the prediction must not
    # write a backend PC entry or advance BPU again.
    assert agent.redirect_event() is not None
    assert not agent.backend_write().wen
    assert not agent.prefetch().valid
    assert not agent.fetch().valid
    await agent.step(1)
    assert agent.pointers().bpu.value == 2
    assert agent.entry(2).start_pc == original

    await agent.complete_offer()
    await agent.release_backend_redirect()
    await agent.step(1)
    assert agent.pointers().bpu.value == 2


@pytest.mark.feature("FTQ-TOP-016")
async def test_redirect_at_the_training_index_keeps_that_entry_trainable(ftq_agent):
    agent = ftq_agent
    await allocate(agent, 6, base=0x8000_4000, step=0x20)
    await agent.resolve([resolve(4, pc=0x8000_4080, offset=1)])
    for _ in range(6):
        if agent.training() is not None:
            break
        await agent.step(1)
    assert agent.training() is not None

    # The redirect target itself (entry 4) is not younger than the redirect,
    # so its predictor update must survive; only strictly younger entries are
    # flushed from the training cache.
    await agent.backend_redirect(BackendRedirect(
        4, pc=0x8000_4080, offset=0, level=1))
    training = agent.training()
    assert training is not None
    assert [branch.position for branch in training.branches] == [1]


@pytest.mark.feature("FTQ-TOP-015")
async def test_resolve_at_the_training_head_delays_its_own_dequeue(ftq_agent):
    agent = ftq_agent
    await agent.consumers(train=1)
    await agent.resolve_hold([resolve(5, pc=0x8000_5000, offset=1, mispredict=0)])
    await agent.step(1)
    await agent.resolve_hold([resolve(5, pc=0x8000_5000, offset=2, mispredict=1)])
    await agent.step(1)
    assert agent.training() is None, (
        "a same-cycle resolve for the dequeue head must suppress the handoff")
    await agent.resolve_release()
    await agent.step(1)
    training = agent.training()
    assert training is not None
    assert [branch.position for branch in training.branches] == [1, 2]


@pytest.mark.feature("FTQ-TOP-013")
async def test_commit_pointer_wraps_and_stops_at_one_lap(ftq_agent):
    agent = ftq_agent
    await allocate(agent, 64, base=0x8000_0000, step=0x20, consume=True)
    assert agent.pointers().bpu.flag == 1
    assert agent.pointers().commit.value == 0

    await agent.commit(63)
    for _ in range(70):
        state = agent.pointers().commit
        if (state.flag, state.value) == (1, 0):
            break
        await agent.step(1)
    state = agent.pointers().commit
    assert (state.flag, state.value) == (1, 0)
    await agent.step(2)
    state = agent.pointers().commit
    assert (state.flag, state.value) == (1, 0)


@pytest.mark.feature("FTQ-TOP-008")
async def test_s3_override_rewinds_already_advanced_prefetch_and_fetch(ftq_agent):
    agent = ftq_agent
    await allocate(agent, 4, step=0x20, with_meta=False)
    await agent.consumers(prefetch=1, mainpipe=1)
    for _ in range(2):
        await agent.step(1)
    assert agent.pointers().pf[0].value >= 2
    assert agent.pointers().fetch[0].value >= 2

    new_pc = 0x8000_1800
    await agent.offer(Prediction(new_pc, taken=1, end_position=5,
                                 s3_override=1, s3_ptr=1))
    await agent.consumers(prefetch=0, mainpipe=0)
    await agent.step(1)
    await agent.complete_offer()
    await agent.step(1)
    state = agent.pointers()
    assert state.bpu.value == 2
    assert state.pf[0].value == 1
    assert state.fetch[0].value == 1
    assert agent.entry(1).start_pc == new_pc


@pytest.mark.feature("FTQ-TOP-015")
@pytest.mark.parametrize("mispredict_slot", range(8))
async def test_first_mispredict_mask_covers_every_branch_slot(ftq_agent, mispredict_slot):
    agent = ftq_agent
    await allocate(agent, 8, base=0x8000_6000, step=0x20)
    pc = 0x8000_6000
    await agent.consumers(train=0)
    # All eight reports are presented while the entry is still the dequeue
    # head, so ResolveQueue keeps them in one training entry.  The predictor
    # update must then stop after the first mispredicted position.
    await agent.resolve_stream([
        [resolve(0, pc=pc, offset=slot,
                 mispredict=1 if slot == mispredict_slot else 0)
         for slot in group]
        for group in (range(0, 3), range(3, 6), range(6, 8))
    ])
    for _ in range(6):
        if agent.training() is not None:
            break
        await agent.step(1)
    training = agent.training()
    assert training is not None
    positions = [branch.position for branch in training.branches]
    assert positions == list(range(mispredict_slot + 1)), positions
    agent.assert_training_mask()
