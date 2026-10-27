"""One capacity boundary, not a physical-bank Cartesian product."""
from bpuverify.bpu.checker.micro_capacity import MicroCapacityChecks
from bpuverify.bpu.env.micro import micro_program


PC = 0x40000800


async def check_micro_capacity(agent,coverage):
    async with micro_program(agent,PC) as env:
        micro = env.micro
        pcs = tuple(PC+index*0x80 for index in range(micro.capacity+1))
        program = {pc:(PC+0x20000+index*0x20,3+8*(index%2)) for index,pc in enumerate(pcs)}
        checks = MicroCapacityChecks(env.checker,program,coverage)

        async def capture(pc,role):
            return await env.capture(pc,lambda source:checks.source(source,pc,role))

        async def train(pc,source):
            target,position = program[pc]
            await env.train(pc,source,target,position)

        for index,pc in enumerate(pcs[:-1],1):
            source = await capture(pc,'cold')
            await train(pc,source)
            checks.check(index,sum(bool(entry.confidence) for entry in micro.entries),'capacity grows by a real source')
        for pc in pcs[:-1]:
            await capture(pc,'initial-resident')
        checks.check(micro.capacity,sum(bool(entry.confidence) for entry in micro.entries),'all entries remain live after public readback')
        new_pc = pcs[-1]
        replacement_source = await capture(new_pc,'cold')
        protected = next(pc for pc in pcs[:-1] if micro._find(pc*2)==micro.victim())
        checks.plan_protection(protected)
        await capture(protected,'protect')
        victim = next(pc for pc in pcs[:-1] if micro._find(pc*2)==micro.victim())
        checks.plan_replacement(victim)
        await train(new_pc,replacement_source)
        checks.replacement_accepted()
        await capture(victim,'evicted')
        await capture(new_pc,'new')
        for pc in pcs[:-1]:
            if pc!=victim:
                await capture(pc,'survivor')
        checks.finish()
        return dict(capacity=micro.capacity,protected=protected,victim=victim,replacement=new_pc,
            public_sources=len(checks.sources),pipeline_cycles=env.checker.counts['cycles'])
