"""One genuine predictor key, two logical confidence buckets; no bank sweep."""
import json
from suites.frontend.bpu.bpu.coverage.tage.selector import SelectorCoverage
from suites.frontend.bpu.bpu.checker.tage.selector import TageSelectorChecker
from suites.frontend.bpu.bpu.monitor.tage.selector import TageSelectorMonitor
from suites.frontend.bpu.bpu.checker.sc.role_scenarios import ZeroHistoryChecker,CombinedChecks
from suites.frontend.bpu.bpu.case.sc.role_scenarios import prepare_pair,revisit,source_pc,neutral_target
from suites.frontend.bpu.bpu.case.abtb.timeouts import bounded
from suites.frontend.bpu.bpu.model.tage.selector import exercise_program
from suites.frontend.bpu.bpu.model.sc.metadata import tage_provider_signatures
from suites.frontend.bpu.bpu.model.sc.provider_roles import validate_transition
from suites.frontend.bpu.bpu.transaction.types import BpuBatchTraining,BpuBranchFeedback


async def check_selector(agent,output):
    pc=0x40010008;positions=(4,5)
    coverage=SelectorCoverage();checker=TageSelectorChecker(coverage)
    phr=ZeroHistoryChecker(scope='real zero-history selector event source',record_limit=64)
    checks=CombinedChecks(checker,phr)
    observation=agent.observe_phr(phr)
    monitor=TageSelectorMonitor(agent)
    stages=[];source_ticks=[]
    async def wait(operation,label):
        return await bounded(agent,checks,operation,label)
    def check_public(source):
        return checker.check_public(source,positions[0],phr=phr,positions=positions,
            targets=tuple(neutral_target(pc,p) for p in positions))
    async with observation:
        monitor.start(agent._execution,observer=checker.capture)
        try:
            await wait(agent.reset(source_pc(pc)),'reset')
            checkpoint=await wait(agent.next_transaction(start_pc=source_pc(pc)),'genuine source checkpoint')
            _,capture,_=await wait(prepare_pair(agent,phr,pc,checkpoint,positions,(4,5)),
                'genuine highest-provider preparation')
            await wait(agent.configure_predictors(sc=False,settle=True),'disable SC selection only')
            capture=await wait(revisit(agent,phr,pc,checkpoint),'fresh TAGE-only source')
            identities=tuple(signature[:2] for signature in tage_provider_signatures(capture,positions))
            checker.check((3,3),tuple(identity[0] for identity in identities),'both_genuine_providers_at_highest_table')
            checker.phase='exercise'
            meta=check_public(capture)
            for label,outcomes in exercise_program():
                checker.phase=label
                before=checker.values
                for taken in outcomes:
                    prior=tage_provider_signatures(capture,positions)
                    predicted=int(meta['providerTakenCtr_value']>=4) if meta['useProvider'] else meta['altOrBasePred']
                    mispredict=int(predicted!=taken)
                    feedback=BpuBatchTraining(pc,capture.meta.resolve,(BpuBranchFeedback(positions[0],
                        neutral_target(pc,positions[0]),1,taken=taken,mispredict=mispredict),))
                    checker.plan(feedback,capture)
                    source_ticks.append(capture.prediction_tick)
                    await wait(agent.train_batch_with_prediction_pause(feedback),'qualified selector feedback')
                    capture=await wait(revisit(agent,phr,pc,checkpoint),'fresh post-commit selector consumer')
                    current=tage_provider_signatures(capture,positions)
                    checker.check(identities,tuple(signature[:2] for signature in current),
                        'highest_provider_identities_do_not_change')
                    validate_transition(prior,current,lane=0,taken=taken,mispredict=mispredict)
                    meta=check_public(capture)
                stages.append(dict(label=label,before=before,after=checker.values,feedbacks=len(outcomes)))
                if label=='lower-saturation':checker.check(0,checker.values[7],'lower_endpoint_held_under_qualified_decrement')
                if label=='upper-sign-crossing':checker.check(16,checker.values[7],'same_high_confidence_selector_crosses_sign')
                if label=='upper-saturation':checker.check(31,checker.values[7],'upper_endpoint_held_under_qualified_increment')
                if label in ('lower-saturation','upper-saturation'):
                    # Reaching the endpoint is not the same as clamping it: the
                    # batch must contain a real vote that asked to move past the
                    # endpoint and was held. Record that event durably, because
                    # the bounded event deque drops older entries later.
                    rule=('lower-saturation' if label.startswith('lower') else 'upper-saturation')
                    hits=[dict(accepted_tick=record.get('accepted_tick'),**event)
                        for record in checker.events for event in (record.get('events') or ())
                        if event.get('rule')==rule and event.get('index')==7]
                    checker.check(True,bool(hits),rule+'_vote_really_overflowed_the_endpoint',
                        endpoint=checker.values[7])
                    stages[-1]['saturation']=hits
            checker.check([16]*6,list(checker.values[:6]),'all_other_logical_selector_registers_unchanged')
            checker.check(len(source_ticks),len(set(source_ticks)),'distinct_actual_prediction_for_every_feedback')
            await wait(agent.set_ready(prediction=False,meta=True),'stop younger prediction work')
            await wait(observation.drain(),'all admitted feedback effects drain')
            result=dict(passed=True,selector=checker.summary(),PHR=phr.summary(),stages=stages,
                distinct_prediction_sources=len(source_ticks),full_FTQ_legality_proven=False,
                independent_full_TAGE_SRAM_reference_claimed=False)
            coverage.require()
            (output/'tage-selector-summary.json').write_text(json.dumps(result,indent=2)+'\n')
            return result
        except BaseException as error:
            (output/'tage-selector-failure.json').write_text(json.dumps(dict(failure=repr(error),phase=checker.phase,
                counters=dict(checker.counts),selectors=checker.values,recent=list(checker.records),
                pending_sources=list(checker.pending),effect=checker.effect,stages=stages),indent=2)+'\n')
            raise
        finally:
            await monitor.aclose()
            coverage.write(output)
