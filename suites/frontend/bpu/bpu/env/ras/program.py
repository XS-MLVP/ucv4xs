"""Reusable source collection/recovery operations, below semantic scenarios."""
from suites.frontend.bpu.bpu.transaction.types import BpuRedirect,BpuTraining
from suites.frontend.bpu.bpu.model.ras.capacity import POSITION


async def revisit_from_redirect(agent,pc,redirect_meta):
    boundary=await agent.redirect(BpuRedirect(pc,redirect_meta))
    return await agent.next_transaction(start_pc=pc,after_tick=boundary)


async def learn_sites(retirement,semantic,start_pc,sites):
    """Learn actual instructions from coherent cold sources, with RAS off."""
    a=retirement.agent
    await semantic.wait(a.reset(start_pc),'reset')
    cold=await semantic.wait(a.next_transaction(start_pc=start_pc),'initial checkpoint')
    await semantic.wait(a.configure_predictors(ubtb=True,abtb=False,tage=False,sc=False,ittage=False,
        ras=False,mbtb=True,settle=True),'prepare Main with RAS disabled')
    sources={}
    for pc,target,kind,action in sites:
        cold=await semantic.wait(revisit_from_redirect(a,pc,cold.meta.redirect),'genuine cold program source')
        sources[pc]=cold
        await semantic.wait(a.train(BpuTraining(pc,POSITION,target,cold.meta.resolve,branch_type=kind,ras_action=action)),
            'learn actual instruction')
    await semantic.wait(a.set_ready(prediction=False,meta=True),'hold preparation tail')
    await semantic.wait(retirement.coherent.drain(),'all preparation sources observed')
    await semantic.wait(a.configure_predictors(ras=True,settle=True),'enable return stack')
    return sources


async def collect(retirement,semantic,pc,action,minimum,boundary):
    agent=retirement.agent
    collected=[await semantic.wait(agent.next_transaction(start_pc=pc,after_tick=boundary),'genuine program source')
        for _ in range(minimum)]
    await semantic.wait(agent.set_ready(prediction=False,meta=True),'hold younger requests')
    await semantic.wait(retirement.coherent.drain(),'all older RAS operations observed')
    rows=list(collected)+[item for item in retirement.phr.association.completed
        if item.prediction_tick>boundary and item.meta.perf.start_pc==pc]
    rows.sort(key=lambda item:item.meta_tick)
    ticks=[item.meta_tick for item in rows]
    retirement.checker.check(len(ticks),len(set(ticks)),phase='unique-drained-sources')
    actual=[row['tick'] for row in retirement.checker.records if row['tick']>boundary
        and row['spec']['valid'] and row['spec']['enable'] and row['spec']['action']==action]
    retirement.checker.check(ticks,actual,phase='every-drained-RAS-operation-has-a-public-source')
    return rows
