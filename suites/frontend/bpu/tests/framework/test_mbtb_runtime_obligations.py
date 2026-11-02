"""Native lifecycle/checker controls, not additional MainBTB hardware credit."""
import asyncio
from contextlib import asynccontextmanager
import pytest
from toffee import Execution,XCommClockBackend,ScoreboardMismatch,DriveStable,RisingEdge,on,ClockCycles
from suites.frontend.bpu.mbtb.agent.main import MbtbAgent
from suites.frontend.bpu.mbtb.transaction.types import MbtbTraining,MbtbBatchTraining,MbtbBranchFeedback,MbtbLookup,MbtbLookupDisposition,MbtbPrediction
from dataclasses import replace
from suites.frontend.bpu.mbtb.transaction.metadata import declared_metadata,metadata_origin
from copy import deepcopy

pytestmark=[pytest.mark.selftest,pytest.mark.dut('mbtb')]


@asynccontextmanager
async def running(factory):
    dut=factory.create('mbtb',coverage_name='mbtb-runtime-control.dat')
    backend=XCommClockBackend(dut.GetXClock())
    try:
        async with Execution(backend,max_batch_ticks=128) as execution:
            agent=MbtbAgent(dut);await agent.start(execution)
            try:yield agent
            finally:await agent.aclose(check=False)
    finally:backend.close()


async def test_identical_inputs_remain_distinct_completed_transactions_and_finish_adds_no_feedback(dut_factory):
    async with running(dut_factory) as agent:
        await agent.reset()
        transfers=[agent.submit_predict(0x80000000) for _ in range(4)]
        for transfer in transfers:await transfer
        before=agent.reference.model.accepted_feedback
        receipt=await agent.finish()
        assert receipt['finished'] and receipt['prediction'].completed==4
        assert len({transfer.sequence_id for transfer in transfers})==4
        assert len({transfer.accepted_event.tick for transfer in transfers})==4
        assert receipt['accepted_feedback']==before==0
        assert (await agent.finish())==receipt
        with pytest.raises(RuntimeError,match='finished'):agent.submit_predict(0x80000000)


async def test_swallowed_default_reference_failure_is_sticky_through_normal_close(dut_factory,monkeypatch):
    async with running(dut_factory) as agent:
        await agent.reset();await agent.predict(0x80000000)
        error=AssertionError('injected default reference failure');injected=[]
        def wrong(*args,**kwargs):injected.append(True);raise error
        monkeypatch.setattr(agent.reference,'_check',wrong)
        with pytest.raises(AssertionError) as caught:await agent.sample_prediction()
        assert caught.value is error and injected
        with pytest.raises(AssertionError) as caught:await agent.aclose()
        assert caught.value is error and not agent._started
        with pytest.raises(AssertionError) as caught:await agent.aclose()
        assert caught.value is error


async def test_closed_continuous_monitor_cannot_finish_successfully(dut_factory):
    async with running(dut_factory) as agent:
        await agent.reset();await agent.reference_monitor.aclose()
        with pytest.raises(AssertionError,match='continuous input and output monitors'):await agent.finish()


async def test_stuck_already_submitted_stage_tail_is_bounded_not_cancelled_as_completion(dut_factory,monkeypatch):
    async with running(dut_factory) as agent:
        await agent.reset()
        async def stuck(_):await asyncio.Future()
        monkeypatch.setattr(agent.consume_driver,'send',stuck)
        await agent.predict(0x80000000)
        with pytest.raises(TimeoutError,match='mbtb.input-stage-tails'):await agent.finish(timeout_cycles=8)
        assert not agent._finished and any(not task.done() for task in agent._lookup_tails)
        with pytest.raises(TimeoutError):await agent.finish()


@pytest.mark.parametrize('pc',(1<<49,(1<<50)-1))
async def test_real_guarded_lookup_preserves_the_high_address_domain(dut_factory,pc):
    async with running(dut_factory) as agent:
        await agent.reset()
        transfer=agent.submit_predict(pc);prediction=await transfer
        assert transfer.request.pc==pc and not any(entry.valid for entry in prediction.entries)
        assert (await agent.finish())['finished']


async def test_guarded_lookup_reconstructs_a_real_trained_target_without_truncating_the_guard(dut_factory):
    async with running(dut_factory) as agent:
        await agent.reset()
        pc,target=0x80000000,0x80002340
        cold=await agent.predict(pc)
        await agent.train(MbtbTraining(pc,target,1,5,3,cold.meta_entries))
        high=await agent.predict((1<<49)+pc)
        active=[entry for entry in high.entries if entry.valid]
        assert len(active)==1 and (active[0].target,active[0].position)==((1<<49)+target,5)
        assert (await agent.finish())['finished']


def training(source):
    return MbtbBatchTraining(0x80000000,source.meta_entries,
        (MbtbBranchFeedback(0x80002340,1,5,3,mispredict=1),None))


@pytest.mark.parametrize('field',('target','taken','position','branch_type','ras_action','mispredict'))
async def test_real_wrong_driver_payload_does_not_redefine_the_independent_input_plan(dut_factory,monkeypatch,field):
    async with running(dut_factory) as agent:
        await agent.reset();cold=await agent.predict(0x80000000);encode=agent._encode_training;injected=[]
        def wrong(tx):
            payload=encode(tx);payload['branches'][0][field]^=1;injected.append(True);return payload
        monkeypatch.setattr(agent,'_encode_training',wrong)
        with pytest.raises(ScoreboardMismatch) as caught:await agent.train_batch(training(cold))
        assert injected and caught.value.name=='mbtb.planned-training-input'
        assert caught.value.context.sequence_id==1
        with pytest.raises(ScoreboardMismatch) as later:await agent.finish()
        assert later.value is caught.value


async def test_equal_real_feedbacks_have_distinct_ids_and_exact_local_terminals(dut_factory):
    async with running(dut_factory) as agent:
        await agent.reset();cold=await agent.predict(0x80000000);tx=training(cold)
        await agent.train_burst((tx,tx));rows=agent.training_inputs.finish()
        assert [row.uid for row in rows]==[1,2]
        assert [row.state for row in rows]==['local-drained']*2
        assert rows[1].offer_tick-rows[0].offer_tick==2
        assert (await agent.finish())['finished']


async def test_valid_feedback_with_only_explicit_empty_resolve_lanes_still_owns_one_input(dut_factory):
    async with running(dut_factory) as agent:
        await agent.reset();cold=await agent.predict(0x80000000)
        await agent.train_batch(MbtbBatchTraining(0x80000000,cold.meta_entries,(None,)*8))
        row,=agent.training_inputs.finish()
        assert row.state=='local-drained' and row.offer_tick is not None
        assert agent.reference.model.accepted_feedback==1
        assert agent.reference.model.state()['populated_cells']==0
        assert (await agent.finish())['finished']


async def test_disabled_real_feedback_is_offered_and_filtered_not_accepted(dut_factory):
    async with running(dut_factory) as agent:
        await agent.reset();cold=await agent.predict(0x80000000)
        await agent.set_enabled(False);await agent.train_batch(training(cold))
        row,=agent.training_inputs.finish()
        assert row.state=='disabled-filtered' and agent.reference.model.accepted_feedback==0
        await agent.set_enabled(True)
        assert (await agent.finish())['finished']


async def test_real_reset_cancels_the_named_accepted_not_yet_drained_feedback(dut_factory):
    async with running(dut_factory) as agent:
        await agent.reset();cold=await agent.predict(0x80000000)
        ids=await agent.issue_training(training(cold))
        assert ids==(1,) and agent.training_inputs.rows[0].state=='accepted'
        await agent.reset();row,=agent.training_inputs.finish()
        assert row.state=='reset-cancelled' and row.offer_epoch<agent.training_inputs.epoch
        assert (await agent.finish())['finished']


async def test_cancelled_unoffered_burst_keeps_exact_cancelled_uids_not_fake_acceptances(dut_factory):
    async with running(dut_factory) as agent:
        await agent.reset();cold=await agent.predict(0x80000000)
        async with agent._execution.paused():
            task=asyncio.create_task(agent.train_burst((training(cold),training(cold))))
            await asyncio.sleep(0)
            assert len(agent.training_inputs.rows)==2
            task.cancel()
            with pytest.raises(asyncio.CancelledError):await task
        assert (await agent.finish())['finished']
        rows=agent.training_inputs.finish()
        assert [row.state for row in rows]==['cancelled-before-offer']*2
        assert all(row.offer_tick is None for row in rows)


async def test_completed_response_dispatches_ready_stage_tails_without_an_extra_edge(dut_factory):
    async with running(dut_factory) as agent:
        await agent.reset()
        transfers=[agent.submit_predict(0x80000000) for _ in range(4)]
        await transfers[-1];tick=agent._execution.backend.tick
        await agent.drain_predictions()
        assert agent._execution.backend.tick==tick
        assert agent.prediction_scoreboard.status.unmatched_observations==0
        assert (await agent.finish())['finished']


@pytest.mark.parametrize('phase',('drive','rise'))
async def test_cancel_preview_and_cancel_after_acceptance_have_different_real_terminals(dut_factory,phase):
    async with running(dut_factory) as agent:
        await agent.reset();cold=await agent.predict(0x80000000);offers=[]
        async def delivered(_):pass
        def capture(event):
            if agent.ports.training.valid.U():offers.append(event.tick)
        subscription=agent._execution.subscribe(on(RisingEdge(agent.dut.clock),
            capture=capture,delivery='lossless',capacity=64)(delivered).bind())
        try:
            async with agent._execution.paused():
                task=asyncio.create_task(agent.train_burst((training(cold),)*4));await asyncio.sleep(0)
            event=await (DriveStable(agent.dut.clock) if phase=='drive' else RisingEdge(agent.dut.clock))
            async with agent._execution.paused():
                task.cancel()
                with pytest.raises(asyncio.CancelledError):await task
            assert (await agent.finish())['finished']
            rows=agent.training_inputs.finish()
            if phase=='drive':
                assert offers==[] and all(row.offer_tick is None for row in rows)
                assert [row.state for row in rows]==['cancelled-before-offer']*4
            else:
                assert offers==[event.tick] and rows[0].offer_tick==event.tick
                assert [row.state for row in rows]==['local-drained']+['cancelled-before-offer']*3
        finally:
            agent._execution.reactor.cancel_subscription(subscription)
            if subscription.task is not None:
                await asyncio.gather(subscription.task,return_exceptions=True)


@pytest.mark.parametrize('mode',('custom-response','acceptance-only'))
async def test_wrong_lookup_pc_cannot_redefine_the_original_even_with_custom_expected(dut_factory,monkeypatch,mode):
    async with running(dut_factory) as agent:
        await agent.reset();encode=agent.lookup_driver.encoder;injected=[]
        def wrong(request):
            injected.append(True);return encode(MbtbLookup(request.pc^0x80))
        monkeypatch.setattr(agent.lookup_driver,'encoder',wrong)
        with pytest.raises(ScoreboardMismatch) as caught:
            if mode=='custom-response':await agent.submit_predict(0x80000000,expected=lambda actual:None)
            else:await agent.launch_lookup(MbtbLookup(0x80000000))
            await agent.finish()
        assert injected and caught.value.name=='mbtb.planned-lookup-input'
        with pytest.raises(ScoreboardMismatch) as later:await agent.finish()
        assert later.value is caught.value


async def test_legitimate_pending_cancel_has_a_named_terminal_and_does_not_fail_the_stage_tail(dut_factory):
    async with running(dut_factory) as agent:
        await agent.reset()
        async with agent._execution.paused():
            cancelled=agent.submit_predict(0x80000000);cancelled.cancel()
            live=agent.submit_predict(0x80000000)
        await live;receipt=await agent.finish()
        assert receipt['finished']
        assert [row['uid'] for row in receipt['lookup_inputs']]==[cancelled.sequence_id,live.sequence_id]
        assert [row['state'] for row in receipt['lookup_inputs']]==['cancelled-before-offer','responded']


@pytest.mark.parametrize('stage',('s0','s1','s2'))
async def test_identical_payloads_cannot_hide_a_missing_original_stage_pulse(dut_factory,monkeypatch,stage):
    async with running(dut_factory) as agent:
        await agent.reset();await agent.predict(0x80000000);await agent.drain_predictions()
        if stage=='s0':
            encode=agent.lookup_driver.encoder
            def missing(request):return dict(encode(request),s0_fire=0)
            monkeypatch.setattr(agent.lookup_driver,'encoder',missing)
        else:monkeypatch.setattr(agent.advance_driver if stage=='s1' else agent.consume_driver,'encoder',lambda _:{'fire':0})
        with pytest.raises(ScoreboardMismatch) as caught:
            await agent.submit_predict(0x80000000,expected=lambda actual:None)
            await agent.finish()
        assert caught.value.name=='mbtb.planned-lookup-input'


async def test_equal_native_metadata_keeps_the_declared_second_lookup_uid_not_the_first_match(dut_factory):
    async with running(dut_factory) as agent:
        await agent.reset()
        first=agent.submit_predict(0x80000000);old=await first
        second=agent.submit_predict(0x80000000);current=await second
        assert old.meta_entries==current.meta_entries
        assert metadata_origin(old.meta_entries).uid==first.sequence_id
        assert metadata_origin(current.meta_entries).uid==second.sequence_id
        await agent.train_batch(training(current));receipt=await agent.finish()
        row,=receipt['training_inputs']
        assert row['metadata_scope']=='verified-isolated-lookup'
        assert row['source']['uid']==second.sequence_id and row['source']['uid']!=first.sequence_id


@pytest.mark.parametrize('fault',('edited-counter','wrong-pc','old-epoch'))
async def test_wrong_native_metadata_ancestor_is_rejected_before_allocating_or_driving_training(dut_factory,fault):
    async with running(dut_factory) as agent:
        await agent.reset();cold=await agent.predict(0x80000000);values=deepcopy(cold.meta_entries)
        pc=0x80000000
        if fault=='edited-counter':values[0][0]['counter_value']^=1
        elif fault=='wrong-pc':pc^=0x80
        else:await agent.reset()
        tx=MbtbBatchTraining(pc,values,(MbtbBranchFeedback(0x80002340,1,5,3,mispredict=1),))
        before=agent._execution.backend.tick
        with pytest.raises(ScoreboardMismatch) as caught:await agent.train_batch(tx)
        assert caught.value.name=='mbtb.training-source-ancestry'
        assert agent.training_inputs.rows==() and agent._execution.backend.tick==before
        # Explicit isolated port replay is still legal and is not promoted to
        # genuine lookup or integrated FTQ provenance by a matching payload.
        if fault=='old-epoch':
            new=await agent.predict(pc);tx=training(new)
        else:
            detached=declared_metadata(values,reason='explicit isolated metadata replay control')
            tx=MbtbBatchTraining(pc,detached,tx.branches)
        await agent.train_batch(tx);assert (await agent.finish())['finished']


@pytest.mark.parametrize('cycles',(0,1,2))
@pytest.mark.parametrize('control',('reset','disable'))
async def test_accepted_lookup_control_change_keeps_produced_results_and_disposes_only_unproduced_ones(dut_factory,cycles,control):
    async with running(dut_factory) as agent:
        await agent.reset();cold=await agent.predict(0x80000000)
        await agent.train(MbtbTraining(0x80000000,0x80002340,1,5,3,cold.meta_entries))
        await agent.predict(0x80000000)
        old=agent.submit_predict(0x80000000);await old.wait_processing()
        if cycles:await ClockCycles(agent.dut.clock,cycles)
        if control=='reset':await agent.reset()
        else:await agent.set_enabled(False);await agent.set_enabled(True)
        value=await old
        if cycles==0:
            assert type(value) is MbtbLookupDisposition
            assert value.reason==('reset-cancelled' if control=='reset' else 'disabled-before-result')
            assert metadata_origin(value.preview.meta_entries) is None
        else:
            assert type(value) is MbtbPrediction
            assert any(entry.valid and entry.target==0x80002340 for entry in value.entries)
            assert metadata_origin(value.meta_entries).uid==old.sequence_id
        fresh=agent.submit_predict(0x80000000);await fresh
        receipt=await agent.finish()
        before=next(row for row in receipt['lookup_inputs'] if row['uid']==old.sequence_id)
        after=next(row for row in receipt['lookup_inputs'] if row['uid']==fresh.sequence_id)
        assert after['state']=='responded' and after['delivery_tick']==after['response_tick']
        if cycles==0:
            assert before['response_tick'] is None and before['terminal_tick']<=before['delivery_tick']
        if control=='reset':assert after['offer_epoch']>before['offer_epoch']


async def test_disabled_lookup_returns_a_checked_terminal_and_never_calls_the_response_callback(dut_factory):
    async with running(dut_factory) as agent:
        await agent.reset();calls=[]
        live=agent.submit_predict(0x80000000,expected=lambda result:calls.append(live.sequence_id));await live
        await agent.set_enabled(False)
        filtered=agent.submit_predict(0x80000000,expected=lambda result:calls.append(filtered.sequence_id))
        result=await filtered
        assert type(result) is MbtbLookupDisposition and result.reason=='disabled-filtered'
        assert calls==[live.sequence_id] and metadata_origin(result.preview.meta_entries) is None
        receipt=await agent.finish()
        assert receipt['prediction'].completed==2
        assert receipt['lookup_deliveries']==dict(effective_responses=1,checked_sdk_results=2,non_response_terminals=1)


@pytest.mark.parametrize('fault',('uid','reason','drop-terminal'))
async def test_custom_expected_cannot_waive_wrong_terminal_and_long_reset_wakes_before_overflow(dut_factory,monkeypatch,fault):
    async with running(dut_factory) as agent:
        await agent.reset();capture=agent.prediction_monitor._capture;injected=[]
        def wrong(event):
            value=capture(event)
            if type(value) is not MbtbLookupDisposition:return value
            injected.append(True)
            if fault=='drop-terminal':return value.preview
            return replace(value,**({'uid':value.uid+100} if fault=='uid' else {'reason':'disabled-filtered'}))
        monkeypatch.setattr(agent.prediction_monitor,'_capture',wrong)
        old=agent.submit_predict(0x80000000,expected=lambda actual:None);await old.wait_processing()
        started=agent._execution.backend.tick
        with pytest.raises(ScoreboardMismatch) as caught:await agent.reset()
        with pytest.raises(ScoreboardMismatch) as repeated:await old
        assert caught.value is repeated.value and injected
        assert agent._execution.backend.tick-started<32


async def test_sdk_completed_does_not_replace_the_actual_terminal_comparison_witness(dut_factory,monkeypatch):
    async with running(dut_factory) as agent:
        await agent.reset();await agent.set_enabled(False)
        monkeypatch.setattr(agent.prediction_scoreboard,'check',lambda **kwargs:None)
        result=await agent.submit_predict(0x80000000)
        assert type(result) is MbtbLookupDisposition
        with pytest.raises(ScoreboardMismatch):await agent.finish()


async def test_custom_expected_cannot_hide_a_corrupted_sdk_sample_even_when_raw_native_output_is_correct(dut_factory,monkeypatch):
    async with running(dut_factory) as agent:
        await agent.reset();capture=agent.prediction_monitor._capture;injected=[]
        def wrong(event):
            value=capture(event)
            if type(value) is MbtbPrediction:
                injected.append(True)
                return MbtbPrediction((replace(value.entries[0],valid=value.entries[0].valid^1),*value.entries[1:]),value.meta_entries)
            return value
        monkeypatch.setattr(agent.prediction_monitor,'_capture',wrong)
        with pytest.raises(ScoreboardMismatch):await agent.submit_predict(0x80000000,expected=lambda actual:None)
        assert injected
