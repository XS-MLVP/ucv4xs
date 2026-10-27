"""Normal opposite prediction epochs, then existing receipt-terminated service."""
from bpuverify.bpu.env.direction_service import prepare_service_stream
from bpuverify.bpu.model.tage.service import STREAM_PC
from bpuverify.bpu.model.tage.dual_migration import PC,PATHS
from bpuverify.bpu.model.tage.asymmetric_retirement import OUTCOMES


async def prepare_direction_turnaround(env,checks):
    if getattr(checks,'prepare_read_stream',True):
        await prepare_service_stream(env,pc=getattr(checks,'stream_pc',STREAM_PC))
    enabled=True
    for step in checks.intents:
        if enabled!=step.enabled:
            await env.enable_tage(step.enabled);enabled=step.enabled
        before_role=getattr(checks,'before_capture_roles',{}).get(step.name)
        if before_role is not None:
            checks.retain_prepared(before_role,await env.capture_via(PC,PATHS[step.context]))
        before=await env.capture_via(PC,PATHS[step.context])
        checks.preparing_input(before,step)
        branches=env.branch_path(step.outcomes)
        event=(await env.resolve(before,*branches) if step.allocation is None else
               await env.allocate(before,*branches,owner=step.allocation))
        after=await env.capture_via(PC,PATHS[step.context])
        checks.prepared(after,step,event);env.checker.retire_source(before.meta_tick)
        role=checks.capture_roles.get(step.name)
        if role is not None:
            checks.retain_prepared(role,after)
            count=getattr(checks,'prepared_source_count',lambda _:1)(role)
            for _ in range(count-1):
                checks.retain_prepared(role,await env.capture_via(PC,PATHS[step.context]))
        elif step.save:
            checks.retain_old(after)
            for _ in range(checks.source_count-1):
                checks.retain_old(await env.capture_via(PC,PATHS['original']))
        else:env.checker.retire_source(after.meta_tick)
    current={name:await env.capture_via(PC,path) for name,path in PATHS.items()}
    checks.arm(current)
    for step in checks.neighbor_intents:
        if enabled!=step.enabled:
            await env.enable_tage(step.enabled);enabled=step.enabled
        before=await env.capture_via(PC,checks.history_paths[step.context])
        checks.neighbor_preparing(before,step)
        branches=env.branch_path(step.outcomes)
        event=(await env.resolve(before,*branches) if step.allocation is None else
               await env.allocate(before,*branches,owner=step.allocation))
        after=await env.capture_via(PC,checks.history_paths[step.context])
        checks.neighbor_prepared(after,step,event)
        env.checker.retire_source(before.meta_tick);env.checker.retire_source(after.meta_tick)
    current={name:await env.capture_via(PC,path) for name,path in checks.history_paths.items()}
    checks.arm_neighbor(current)
    warm=await env.capture_via(PC,checks.history_paths['original'])
    event=await env.resolve(warm,*env.branch_path(OUTCOMES[1]))
    current={name:await env.capture_via(PC,path) for name,path in checks.history_paths.items()}
    checks.arm_asymmetric(warm,event,current);env.checker.retire_source(warm.meta_tick)
