"""Unique outstanding public predictions drive threshold range rejection."""
from dataclasses import asdict
import json
from bpuverify.bpu.transaction.types import BpuBatchTraining,BpuBranchFeedback
from bpuverify.bpu.model.sc.bounds import bounds_plan,public_decisions
from bpuverify.bpu.model.sc.metadata import tage_provider_signatures,mbtb_meta_for_position,sc_decisions_for_positions
from bpuverify.bpu.model.sc.used import branch_effects,threshold_update,INITIAL
from bpuverify.bpu.case.sc.role_scenarios import prepare_pair,source_pc,revisit,neutral_target
from bpuverify.bpu.checker.sc.role_scenarios import ZeroHistoryChecker
from bpuverify.bpu.checker.sc.full import FullScChecker
from bpuverify.bpu.monitor.sc.full import FullScMonitor
from bpuverify.bpu.checker.sc.common_state import CommonStateChecker
from bpuverify.bpu.monitor.sc.common_state import CommonStateMonitor
from bpuverify.bpu.checker.sc.common_routes import RouteChecker
from bpuverify.bpu.monitor.sc.common_routes import CommonHistoryMonitor
from bpuverify.bpu.coverage.sc.bounds import ThresholdCoverage
from bpuverify.bpu.case.sc.scenarios import bounded
from bpuverify.common.monitor.activity import TRAINING_TIMEOUT_CYCLES


def bounds_feedback(plan,capture,*,count,taken):
    if type(count) is not int or count not in (1,2):
        raise ValueError('one/two distinct branches and one-bit outcomes required')
    outcomes=(taken,)*count if type(taken) is int else taken
    if type(outcomes) is not tuple or len(outcomes)!=count or any(type(v) is not int or v not in (0,1) for v in outcomes):
        raise ValueError('one/two distinct branches and one-bit outcomes required')
    if any(outcomes[:-1]):
        raise ValueError('a taken branch cannot precede another resolved branch')
    pc=plan['pc'];positions=plan['positions'];branches=[];reported_mispredict=False
    for p,taken in zip(positions[:count],outcomes,strict=True):
        slot,_=mbtb_meta_for_position(capture,p);sc=capture.meta.resolve['sc']
        predicted=sc['scPred'][slot] if sc['useScPred'][slot] else sc['tagePred'][slot]
        mispredict=bool(predicted!=taken and not reported_mispredict)
        reported_mispredict|=mispredict
        branches.append(BpuBranchFeedback(p,pc if p==positions[0] else neutral_target(pc,p),
            1,taken=taken,mispredict=int(mispredict)))
    return BpuBatchTraining(pc,capture.meta.resolve,tuple(branches))


async def check_bounds(agent,output,*,way,boundary):
    plan=bounds_plan(way,boundary);pc=plan['pc'];positions=plan['positions']
    budget=1024+plan['requests']*8
    coverage=ThresholdCoverage()
    checker=FullScChecker(plan,capacity=budget,record_limit=64,threshold_coverage=coverage)
    phr=ZeroHistoryChecker(scope='real zero-path-hash threshold feedback',record_limit=64)
    common=CommonStateChecker(record_limit=64)
    routes=RouteChecker(phr,record_limit=64)
    observation=agent.observe_phr(phr)
    monitor=FullScMonitor(agent)
    common_monitor=CommonStateMonitor(agent);route_monitor=CommonHistoryMonitor(agent)
    completed=[];sources=[];stages=[]

    def check_failure():
        for item in (checker,phr,common,routes):item.raise_failure()

    def feedback(capture,*,count,taken):
        return bounds_feedback(plan,capture,count=count,taken=taken)

    async def drive(transactions,label):
        checker.phase=label
        before=list(checker.threshold.values);expected=tuple(before)
        for tx in transactions:expected=threshold_update(expected,branch_effects(asdict(tx)))['after']
        first=len(checker.accepts)
        checker.plan(transactions)
        ticks=await bounded(agent.dut.clock,agent.train_batches_with_prediction_pause(tuple(transactions)),
            cycles=2*len(transactions)+TRAINING_TIMEOUT_CYCLES,checker=checker,label=label)
        check_failure()
        checker.check(list(ticks),[r['tick'] for r in checker.accepts[first:]],field='every_driver_monitor_accept_aligned')
        checker.check(expected,checker.threshold.values,field='full_threshold_vector_after_actual_drain')
        completed.extend(transactions)
        stages.append(dict(label=label,count=len(transactions),before=before,after=list(expected),
            first_tick=ticks[0],last_tick=ticks[-1]))

    async with observation:
        monitor.start(agent._execution,observer=checker.capture,controls=checker.capture_controls)
        common_monitor.start(agent._execution,observer=common.capture)
        route_monitor.start(agent._execution,observer=routes.capture)
        try:
            await agent.reset(source_pc(pc))
            checkpoint=await agent.next_transaction(start_pc=source_pc(pc))
            cold,capture,_=await prepare_pair(agent,phr,pc,checkpoint,positions,(5,4),
                targets=(pc,neutral_target(pc,positions[1])))
            providers=tage_provider_signatures(capture,positions)
            if boundary=='lower':
                await agent.configure_predictors(tage=False,settle=True)
                await drive((feedback(capture,count=2,taken=0),),'prime-negative-SC')
                await agent.configure_predictors(tage=True,settle=True)
                capture=await revisit(agent,phr,pc,checkpoint)
            checker.check((plan['start'],)*1,tuple(checker.threshold.values[way:way+1]),field='independent_initial_threshold_after_optional_prime')
            checker.phase='capture-outstanding'
            captures=[]
            for _ in range(plan['requests']):
                capture=await agent.next_transaction(start_pc=pc,after_tick=capture.prediction_tick)
                check_failure()
                checker.check(providers,tage_provider_signatures(capture,positions),field='genuine_original_provider_pair')
                checker.check(((plan['initial_sc'],0,0),)*2,sc_decisions_for_positions(capture,positions),field='real_low_confidence_public_SC_snapshot')
                captures.append(capture);sources.append(capture.prediction_tick)
            checker.check(len(sources),len(set(sources)),field='unique_actual_request_for_every_feedback')
            await agent.set_ready(prediction=False,meta=True)
            await observation.drain()
            await agent.configure_predictors(tage=False,settle=True)
            outward=plan['initial_sc'] if boundary=='lower' else 1-plan['initial_sc']
            inward=1-outward
            offset=0
            # One single vote selects the required odd near-bound value;
            # all remaining approach beats use two distinct resolved branches.
            for start in range(0,plan['approach_requests'],agent.training_driver.capacity):
                stop=min(start+agent.training_driver.capacity,plan['approach_requests'])
                await drive(tuple(feedback(captures[i],count=1 if i==0 else 2,taken=outward)
                    for i in range(start,stop)),'approach')
            offset=plan['approach_requests']
            checker.check(plan['near'],checker.threshold.values[way],field='one_inside_architectural_bound')
            await drive((feedback(captures[offset],count=2,taken=(0,1)),),'opposed-votes-interior');offset+=1
            checker.check(plan['near'],checker.threshold.values[way],field='qualified_opposed_votes_cancel_interior')
            for step in range(4):
                await drive((feedback(captures[offset],count=2,taken=outward),),'reject-whole-two-vote-update')
                offset+=1
                checker.check(plan['near'],checker.threshold.values[way],field='reject_not_clamp_to_bound')
            await drive((feedback(captures[offset],count=1,taken=inward),),'recover-inward');offset+=1
            checker.check(plan['near']-plan['outward'],checker.threshold.values[way],field='inward_recovery_after_whole_rejection')
            for _ in range(2):
                await drive((feedback(captures[offset],count=1,taken=outward),),'inclusive-bound-approach');offset+=1
            checker.check(plan['bound'],checker.threshold.values[way],field='inclusive_bound_accepted')
            await drive((feedback(captures[offset],count=2,taken=(0,1)),),'opposed-votes-at-bound');offset+=1
            checker.check(plan['bound'],checker.threshold.values[way],field='aggregate_opposed_votes_before_custom_range_check')
            await drive((feedback(captures[offset],count=1,taken=outward),),'single-vote-bound-reject');offset+=1
            checker.check(plan['bound'],checker.threshold.values[way],field='inclusive_bound_outward_vote_rejected')
            await drive((feedback(captures[offset],count=1,taken=inward),),'leave-inclusive-bound');offset+=1
            checker.check(plan['bound']-plan['outward'],checker.threshold.values[way],field='inclusive_bound_inward_vote_recovers')
            checker.check(len(captures),offset,field='every_unique_captured_request_consumed_once')
            checker.check([INITIAL]*3,[v for i,v in enumerate(checker.threshold.values) if i!=way],field='all_other_global_thresholds_held')
            await agent.pause_prediction_reads()
            check_failure()
            await agent.configure_predictors(tage=True,settle=True)
            await agent.set_ready(prediction=True,meta=True)
            final=await revisit(agent,phr,pc,checkpoint)
            checker.check(providers,tage_provider_signatures(final,positions),field='held_real_providers_survive_boundary_sequence')
            expected_public=public_decisions(checker.reference,pc,positions,providers,checker.threshold.values,
                final.meta.resolve['commonHR'])
            checker.check(expected_public,sc_decisions_for_positions(final,positions),field='fresh_public_SC_decisions_from_full_reference_SRAM')
            await agent.set_ready(prediction=False,meta=True)
            await observation.drain()
            check_failure()
            summary=checker.summary();phr_summary=phr.summary()
            coverage.require_bounds(way,boundary)
            result=dict(passed=True,plan=plan,SC=summary,PHR=phr_summary,common=common.summary(),
                route_checks=routes.scoreboard.status.checked,unique_requests=len(sources),
                source_ticks=dict(first=sources[0],last=sources[-1]),stages=stages,
                retained_frames=dict(sc=len(checker.records),controls=len(checker.control_records),phr=len(phr.records)),
                final_public=dict(expected=expected_public,actual=sc_decisions_for_positions(final,positions)),
                full_FTQ_legality_proven=False,independent_IMLI_reference_claimed=False)
            (output/f'sc-bounds-{way}-{boundary}-summary.json').write_text(json.dumps(result,indent=2)+'\n')
            return result
        except BaseException as error:
            coverage.fail(error)
            (output/f'sc-bounds-{way}-{boundary}-failure.json').write_text(json.dumps(dict(failure=repr(error),
                plan=plan,requests_captured=len(sources),feedback_completed=len(completed),stages=stages,
                SC_failure=repr(checker.failure),PHR_failure=repr(phr.failure),common_failure=repr(common.failure),
                threshold_events=coverage.summary()),indent=2)+'\n')
            raise
        finally:
            await monitor.aclose();await common_monitor.aclose();await route_monitor.aclose()
            coverage.write(output,way,boundary)
