"""Public normal learning operations, with both learners active in the core."""
from bpuverify.bpu.env.sc_loop_experience import Environment as LoopEnvironment


class Environment(LoopEnvironment):
    async def younger(self,source):
        return await super().younger(source,learn_tage=True)

    async def establish_joint_experience(self):
        c,p=self.checks,self.checks.program
        cold=await self.prepare()
        young=await self.younger(cold)
        c.young_private_before=c.bank.statistical_snapshot(c.save(young)).read.weights[3]
        await self.feedback_original(cold,True,'used-cold')
        c.expected_provider=6
        after=await self.query_iteration(p.old_iteration)
        c.provider(after);value=c.consume(after,p.old_iteration,'after-cold')
        c.check(True,all(a!=b for a,b in zip(c.cold_read.weights,value.original.read.weights,strict=True)),
            'the first actual joint outcome reaches both new direction and all correction features')
        c.mark('joint-cold-teaches-both')
        # The joint cold result must use a still-live PHR source. Later
        # low-confidence originals are needed only for SC preparation.
        rest=[after,*[await self.query_iteration(p.old_iteration) for _ in range(p.teaching_count-2)]]
        for source in rest:
            slot,value=c.provider(source)
            c.check(0,value.prediction.used[slot],'all preparation originals are captured before further SC teaching')
        c.warm_sources=(cold,*rest)
        await self.controls(tage=False)
        for i,source in enumerate(c.warm_sources[1:],1):
            await self.feedback_original(source,True,f'teaching-{i}')
        await self.controls(tage=True)
        strong=await self.query_iteration(p.old_iteration)
        slot,value=c.provider(strong)
        c.check((1,1,1),(value.prediction.used[slot],value.prediction.directions[slot],value.prediction.above[slot]),
            'real independent cold originals establish correction authority at the new TAGE confidence')
        c.consume(strong,p.old_iteration,'strong');c.mark('strong-loop-consumer')
        return strong
