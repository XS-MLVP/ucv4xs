"""One capacity lifecycle, with two semantically distinct reset-trigger contexts."""
import json
from suites.frontend.bpu.bpu.model.tage.aging import MAX_FAILURES
from suites.frontend.bpu.bpu.coverage.tage.aging import AgingCoverage
from suites.frontend.bpu.bpu.checker.tage.aging import TageAgingChecker
from suites.frontend.bpu.bpu.monitor.tage.aging import TageAgingMonitor
from suites.frontend.bpu.bpu.checker.sc.role_scenarios import ZeroHistoryChecker,CombinedChecks
from suites.frontend.bpu.bpu.case.sc.role_scenarios import revisit,source_pc,neutral_target
from suites.frontend.bpu.bpu.case.abtb.timeouts import bounded
from suites.frontend.bpu.bpu.model.sc.metadata import mbtb_counter_for_position,tage_meta_for_position
from suites.frontend.bpu.bpu.transaction.types import BpuBatchTraining,BpuBranchFeedback


async def check_aging(agent,output,trigger):
    if trigger not in ('demand','correct-update'):raise ValueError('unknown semantic reset trigger')
    coverage=AgingCoverage();checker=TageAgingChecker(coverage,trigger)
    phr=ZeroHistoryChecker(scope='genuine candidate-capacity aging lifecycle',record_limit=64)
    checks=CombinedChecks(checker,phr);monitor=TageAgingMonitor(agent)
    pcs=tuple(0x40010008+2048*i for i in range(17));position=4;checkpoints={};residents=[];enabled=False
    protected_per_table={table:0 for table in range(8)}
    async def wait(operation,label):return await bounded(agent,checks,operation,label)
    async def configure(active):
        nonlocal enabled
        await wait(agent.configure_predictors(ubtb=False,abtb=False,mbtb=True,tage=active,
            sc=False,ittage=False,ras=False,settle=True),'normal CSR controls applied')
        enabled=active
    async def fresh(pc):
        actual=await wait(revisit(agent,phr,pc,checkpoints[pc]),'fresh actual prediction and metadata')
        if enabled:checker.public(actual,pc,position,neutral_target(pc,position),phr)
        return actual
    async def feedback(pc,source,taken):
        tx=BpuBatchTraining(pc,source.meta.resolve,(BpuBranchFeedback(position,neutral_target(pc,position),1,
            taken=taken,mispredict=int(checker.direction(source,phr)!=taken)),))
        checker.plan(tx,source,enabled=enabled)
        await wait(agent.train_batch_with_prediction_pause(tx),'feedback, SRAM writes and global maintenance complete')
        return await fresh(pc)
    async def install_owner(pc):
        await configure(False);source=await fresh(pc)
        source=await feedback(pc,source,1)
        for _ in range(3):
            prior=mbtb_counter_for_position(source,position)
            if prior==3:return source
            source=await feedback(pc,source,1)
            checker.check(min(3,prior+1),mbtb_counter_for_position(source,position),'real_base_counter_update')
        raise AssertionError('real MainBTB base failed to reach positive saturation')
    async with agent.observe_phr(phr) as observation:
        monitor.start(agent._execution,observer=checker.capture)
        try:
            await wait(agent.reset(source_pc(pcs[0])),'genuine hardware reset')
            for pc in pcs:checkpoints[pc]=await wait(agent.next_transaction(start_pc=source_pc(pc)),'real zero-history checkpoint')
            for pc in pcs[:-1]:
                checker.phase='protect-candidate'
                await install_owner(pc);await configure(True);source=await fresh(pc)
                checker.check(0,tage_meta_for_position(source,position)['hasProvider'],'unique_new_tag')
                source=await feedback(pc,source,0)
                checker.check(3,tage_meta_for_position(source,position)['providerTakenCtr_value'],'real_weak_negative_allocation')
                table=tage_meta_for_position(source,position)['providerTableIdx']
                confidence=protected_per_table[table]
                checker.check(True,confidence in (0,1),'two_capacity_objects_per_history_table')
                if confidence:
                    await install_owner(pc);await configure(True);source=await fresh(pc)
                else:
                    checker.check(2,mbtb_counter_for_position(source,position),'genuine_weak_positive_base_after_allocation')
                checker.check((table,confidence,1,0),(
                    tage_meta_for_position(source,position)['providerTableIdx'],
                    tage_meta_for_position(source,position)['altConf'],
                    tage_meta_for_position(source,position)['altOrBasePred'],
                    tage_meta_for_position(source,position)['hasAlt']),
                    'actual_provider_identity_and_base_confidence_route')
                source=await feedback(pc,source,0)
                meta=tage_meta_for_position(source,position)
                checker.check((2,1),(meta['providerTakenCtr_value'],meta['providerUsefulCtr_value']),'real_correct_disagreement_protects_entry')
                protected_per_table[table]+=1
                residents.append(dict(pc=pc,position=position,target=neutral_target(pc,position)))
            checker.check([2]*8,list(protected_per_table.values()),'both_base_confidences_at_all_provider_tables')
            checker.check([15]*16,list(checker.selector.values),'every_logical_selector_decremented_once_and_others_isolated')
            checker.routing.require()
            checker.check(16,sum(c['valid'] and c['useful']>0 for table in checker.cells for c in table),'all_sixteen_candidate_ways_protected')
            pc=pcs[-1];await install_owner(pc);await configure(True);source=await fresh(pc)
            checker.phase='qualified-failures'
            for event in range(MAX_FAILURES):
                checker.check(0,tage_meta_for_position(source,position)['hasProvider'],'pressure_tag_remains_unallocated')
                source=await feedback(pc,source,1-checker.direction(source,phr))
                checker.check(event+1,checker.counter,'one_counter_increment_per_actual_qualified_failure')
            checker.check(0,checker.epochs,'saturation_alone_does_not_start_maintenance_without_T3')
            checker.phase='saturated-trigger'
            if trigger=='correct-update':
                pc=pcs[0];await install_owner(pc);await configure(True);source=await fresh(pc)
                checker.check(0,checker.direction(source,phr),'correct_negative_provider_trigger')
                source=await feedback(pc,source,0)
            else:source=await feedback(pc,source,1-checker.direction(source,phr))
            checker.check((1,0,0,1),(checker.epochs,checker.counter,checker.busy,checker.counts['clear_completed']),
                'committed_wait_includes_the_actual_all_table_clear')
            checker.check([0]*16,[c['useful'] for table in checker.cells for c in table],'global_clear_discards_normal_useful_update')
            checker.phase='reopened-allocation';pc=pcs[-1];source=await fresh(pc)
            source=await feedback(pc,source,1-checker.direction(source,phr))
            checker.check(1,tage_meta_for_position(source,position)['hasProvider'],'genuine_new_provider_after_clear')
            checker.phase='survivor-consumers';survivors=0
            for resident in residents:
                pc=resident['pc'];await install_owner(pc);await configure(True);source=await fresh(pc)
                meta=tage_meta_for_position(source,position)
                if meta['hasProvider']:survivors+=1
            checker.check(15,survivors,'one_replacement_and_fifteen_expected_old_tags_preserved')
            await wait(agent.set_ready(prediction=False,meta=True),'stop younger prediction work')
            await wait(observation.drain(),'all admitted sources effects and maintenance drain')
            result=dict(passed=True,trigger=trigger,aging=checker.summary(),PHR=phr.summary(),survivors=survivors,
                full_FTQ_legality_proven=False,full_MainBTB_or_all_TAGE_SRAM_reference_claimed=False)
            (output/f'tage-useful-aging-{trigger}-summary.json').write_text(json.dumps(result,indent=2)+'\n')
            return result
        except BaseException as error:
            (output/f'tage-useful-aging-{trigger}-failure.json').write_text(json.dumps(dict(failure=repr(error),
                phase=checker.phase,counts=dict(checker.counts),counter=checker.counter,cells=checker.cells,
                recent=list(checker.records),events=list(checker.events)),indent=2)+'\n')
            raise
        finally:
            await monitor.aclose();coverage.write(output);checker.routing.write(output)
