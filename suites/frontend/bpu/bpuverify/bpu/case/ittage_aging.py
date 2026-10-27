"""Two real contexts, one global tick/maintenance lifecycle; no address sweep."""
from dataclasses import replace
import json
from bpuverify.bpu.checker.ittage_aging import IttageAgingChecker
from bpuverify.bpu.checker.ittage_region import DirectoryPhrChecks
from bpuverify.bpu.coverage.ittage_aging import AgingCoverage
from bpuverify.bpu.model.ittage import IttageContextModel
from bpuverify.bpu.model.ittage_aging import MAX_TICK,SETS
from bpuverify.bpu.monitor.ittage_aging import IttageAgingMonitor
from bpuverify.bpu.monitor.ittage_semantic import IttageSemanticComponentMonitor
from bpuverify.bpu.checker.ittage_semantic import IttageSemanticComponentChecker
from bpuverify.bpu.env.bypass.program import ProgramEnvironment
from bpuverify.bpu.transaction.types import BpuBatchTraining,BpuBranchFeedback


async def check_aging(agent,output):
    coverage=AgingCoverage();checker=IttageAgingChecker(coverage);monitor=IttageAgingMonitor(agent)
    semantic=IttageSemanticComponentChecker(audit=checker);semantic_monitor=IttageSemanticComponentMonitor(agent)
    phr=DirectoryPhrChecks(scope='real ITTAGE tick/useful maintenance')
    pcs=(0x40000806,0x40000816);position=7;targets=(0x40002000,0x40004000,0x40006000)
    models={pc:IttageContextModel() for pc in pcs}
    async with agent.observe_phr(phr) as observation:
        env=ProgramEnvironment(agent,phr,observation,{})
        async def wait(operation,label):
            result=await env.wait(operation,label);checker.raise_failure();semantic.raise_failure();return result
        async def fresh(pc,*,after_clear=False,had_useful=False):
            source=await wait(env.capture(dict(pc=pc),'genuine zero-history predictor key'),'fresh source')
            meta=source.meta.resolve['phr']
            history=(phr.reference.physical_read(meta['phrPtr'])&~8191)|meta['phrLowBits']
            checker.check(0,history,'independent zero PHR context before public comparison')
            models[pc],baseline=semantic.source_context(source)
            if models[pc].entries:
                checker.public(source,pc,models[pc],phr,feedback_target=baseline,position=position,
                    after_clear=after_clear,had_useful=had_useful)
            return source
        async def send(pc,source,target,*,stream=False):
            model=models[pc];mispredict=int(model.target()!=target)
            tx=BpuBatchTraining(pc,source.meta.resolve,(BpuBranchFeedback(position,target,3,taken=1,mispredict=mispredict),))
            checker.check(pc>>19,target>>19,'all targets remain in the real PC region')
            checker.plan(tx,source)
            if stream:await wait(agent.train_batches((tx,)),'actual streaming update, not maintenance completion')
            else:await wait(agent.train_batch_with_prediction_pause(tx),'read-free actual commit and maintenance completion')
        def wrong(pc):
            model=models[pc];provider=model.entries[max(model.entries)].target
            return next(target for target in targets if target not in (provider,model.target()))
        async def prepare(pc,*,require_alternate=False):
            source=await fresh(pc)
            if require_alternate:
                # Allocation proposal is an explicit input to feedback, not a modeled LFSR.
                # Qualify a cold source capable of leaving longer history for an alternate.
                for _ in range(64):
                    if source.meta.resolve['ittage']['allocate']['valid'] and source.meta.resolve['ittage']['allocate']['bits']<len(SETS)-1:break
                    source=await fresh(pc)
                else:raise AssertionError('cold lower-history allocation opportunity not reached')
            for target in targets:
                await send(pc,source,target);source=await fresh(pc)
                if max(models[pc].entries)==len(SETS)-1 and (not require_alternate or len(models[pc].entries)>1):return source
            raise AssertionError('highest real provider with required alternate not established')
        monitor.start(checker)
        semantic_monitor.start(semantic)
        try:
            await wait(env.bootstrap(tuple(dict(pc=pc) for pc in pcs)),'reset and real checkpoints')
            await wait(agent.configure_predictors(ittage=True,settle=True),'apply enabled predictor CSR')
            checker.phase='prepare-primary';primary=await prepare(pcs[0],require_alternate=True)
            await send(pcs[0],primary,wrong(pcs[0]));primary=await fresh(pcs[0])
            checker.check(1,checker.counter,'genuine qualified no-allocation increment')
            checker.phase='prepare-retained-sentinel';sentinel=await prepare(pcs[1],require_alternate=True)
            await send(pcs[1],sentinel,models[pcs[1]].entries[max(models[pcs[1]].entries)].target)
            sentinel=await fresh(pcs[1])
            checker.check(1,sentinel.meta.resolve['ittage']['providerUsefulCnt_value'],'genuine nonzero useful retained sentinel')
            checker.check(True,checker.counts['effective_decrements']>0,'successful allocation truly decreases an existing tick')
            checker.phase='zero-confidence-exclusion'
            await send(pcs[0],primary,wrong(pcs[0]));primary=await fresh(pcs[0])
            checker.check(0,primary.meta.resolve['ittage']['providerCnt_value'],'real unconfident provider')
            await send(pcs[0],primary,models[pcs[0]].entries[max(models[pcs[0]].entries)].target)
            primary=await fresh(pcs[0])
            checker.check(True,checker.counts['correct-unconfident-suppressed']>0,'provider-correct weak exclusion is actually reached')
            checker.phase='qualified-pressure'
            for _ in range(MAX_TICK+2):
                if checker.counter==MAX_TICK-1:break
                await send(pcs[0],primary,wrong(pcs[0]));primary=await fresh(pcs[0])
            else:raise AssertionError('qualified tick saturation input budget exhausted')
            checker.phase='maintenance-read-pressure'
            await send(pcs[0],primary,wrong(pcs[0]),stream=True)
            checker.check(1,checker.counts['epochs'],'one saturation-triggered clear, no extra trigger feedback')
            primary=await fresh(pcs[0])
            checker.check(True,any(busy for busy,index in checker.tables),'maintenance remains pending under real read pressure')
            checker.phase='maintenance-update-priority'
            await send(pcs[0],primary,models[pcs[0]].target(),stream=True)
            checker.check(True,checker.counts['read-blocked']>0 and checker.counts['update-blocked']>0,'genuine read and update priority during maintenance')
            await wait(agent.set_ready(prediction=False,meta=True),'read-free maintenance window')
            await wait(agent.wait_training(committed=True),'all needReset flags and write buffers truly drain')
            await wait(observation.drain(),'accepted public effects drained')
            checker.finish_maintenance()
            await wait(agent.set_ready(prediction=True,meta=True),'resume retained-context consumers after maintenance')
            checker.phase='retained-consumers'
            for pc in pcs:await fresh(pc,after_clear=True,had_useful=pc==pcs[1])
            await wait(agent.set_ready(prediction=False,meta=True),'stop younger consumers')
            await wait(observation.drain(),'final consumer drain')
            summary=checker.summary();phr.summary();coverage.require()
            (output/'ittage-aging-summary.json').write_text(json.dumps(dict(passed=True,aging=summary,
                contexts={pc:models[pc].metadata() for pc in pcs},semantic=semantic.summary(),
                full_FTQ_legality_proven=False),indent=2)+'\n')
        except BaseException as error:
            (output/'ittage-aging-failure.json').write_text(json.dumps(dict(failure=repr(error),phase=checker.phase,
                counter=checker.counter,counts=dict(checker.counts),tables=checker.tables,
                records=list(checker.records),events=list(checker.events)),indent=2)+'\n')
            raise
        finally:
            await semantic_monitor.aclose();await monitor.aclose();coverage.write(output)
