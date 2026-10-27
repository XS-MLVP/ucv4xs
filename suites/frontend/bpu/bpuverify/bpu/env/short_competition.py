"""Normal program steering and original-based completion predicates."""
from bpuverify.bpu.env.short_context_ownership import ShortContextEnv


class Environment(ShortContextEnv):
    async def settle(self):
        await super().settle()
        await self.observation.wait('competition-long-effects-compared',lambda checker:not self.checks.pending_long)

    async def guide(self,branch,*,base,taken):
        view=await self.base(branch,taken=base)
        await view.set_main(early=taken,target=False)
        await self.settle()
        return view

    async def query(self,path,expected,*,base,taken,public_taken=None,phase):
        view=await self.guide(path.branch,base=base,taken=taken)
        self.checks.phase=phase
        source=await view.visit(path)
        self.checks.inspect(source,path,expected,public_taken=(taken if public_taken is None else public_taken))
        await self.settle()
        return source

    async def stabilize_old(self):
        p,c=self.program,self.checks
        path=p.original(p.old);counter=7 if p.old_taken else 0
        for _ in range((7+1)+(3+1)):
            view=await self.guide(p.old,base=not p.old_taken,taken=p.old_taken)
            c.phase='normal-old-owned-confidence-and-protection'
            source=await view.visit(path)
            await self.settle()
            if c.active_owner==p.old and c.states()[p.old]==(counter,3):
                c.inspect(source,path,(0,c.window_states[self.checks.pipeline.source_token(source).history.sequence][0],p.old_taken),
                    public_taken=p.old_taken)
                return
        raise AssertionError('genuine old original feedback did not establish strong protected experience')

    async def storage(self,phase):
        view=self.active
        await view.visit(self.program.helper(view.program.branch))
        await self.settle()
        index=self.program.original(self.program.old).read_indices[0]
        def complete(checker):
            short=checker.model.sources.short
            dirty=any(version.sequence in short.updates[0].dirty and version.index==index for version in short.updates[0].outstanding)
            return short.offered is None and short.learning is None and not dirty and self.checks.pending_protection is None and not self.checks.pending_long
        await self.observation.wait('competition-shared-SRAM-service-completed',complete)
        self.checks.check_storage(phase)
