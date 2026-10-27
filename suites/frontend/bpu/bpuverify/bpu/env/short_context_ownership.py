"""Two actual branch programs share one DUT, reference and passive monitor."""
from contextlib import asynccontextmanager

from bpuverify.bpu.bundle.history_working_set import history_working_set_binding
from bpuverify.bpu.checker.phr.checking import BpuPhrChecker
from bpuverify.bpu.checker.short_context_ownership import ShortContextChecks
from bpuverify.bpu.env.history_working_set import HistoryWorkingSetEnv
from bpuverify.bpu.env.pipeline import PipelineObservation
from bpuverify.bpu.model.ahead_working_set import Edge
from bpuverify.bpu.model.early_direction_sources import EarlyDirectionSources
from bpuverify.bpu.model.history_working_set import FALLBACK, SHORT_POSITION
from bpuverify.bpu.model.short_context_ownership import OWNERS


class ShortContextEnv:
    def __init__(self, agent, observation, source, program, checks):
        self.agent,self.observation,self.program,self.checks = agent,observation,program,checks
        self.views = {}
        self.active = None
        self.initial = source

    async def settle(self):
        await self.active.pause()
        def complete(checker):
            short = checker.model.sources.short
            return (short.offered is None and short.learning is None
                    and self.checks.pending_protection is None)
        await self.observation.wait('short-context-original-learning-compared',complete,timeout_cycles=64)

    async def select(self, branch):
        if branch not in OWNERS: raise ValueError('one declared logical branch required')
        if self.active is not None and self.active.program.branch == branch:
            return self.active
        target = self.program.helper(branch).branch_pc
        if self.active is None:
            source = self.initial
        else:
            await self.settle()
            source = await self.active.go(self.active.source,Edge(self.active.pc,target,3,FALLBACK))
        fresh = branch not in self.views
        if fresh:
            view = HistoryWorkingSetEnv(self.agent,self.observation,source,self.program.view(branch),
                self.checks,anchor_pc=target)
            self.views[branch] = view
        else:
            view = self.views[branch]
            view.source = source
        self.active = view
        # Common predecessor instructions can have been retargeted by the
        # other branch. Their new real outcomes must be reinstalled, not
        # inferred from a per-view Python cache.
        for cached in self.views.values():
            cached.tail_variant = cached.installed_path = None
        if fresh:
            await view.pause()
            await view.bootstrap()
        else:
            # Restore the actual shared predecessor instructions BEFORE Main
            # steering tries to obtain another natural occurrence here.
            # Clearing a Python cache does not retarget the program.
            await view.visit(self.program.helper(branch))
            await self.settle()
        return view

    async def learn_branch(self, branch):
        view = await self.select(branch)
        await view.set_main(early=False,target=False)
        path = next(path for path in self.program.paths if path.branch==branch)
        def qualified(source):
            value = view.snapshot_provider(source,SHORT_POSITION)
            return value is not None and value[0]==0 and not value[2]
        source = await view.learn_until(path,qualified,'normal original learning has a genuine short NT consumer')
        await self.settle()
        self.checks.provider(source,path)

    async def base(self, branch, *, taken):
        view = await self.select(branch)
        await view.set_main(early=taken,target=False)
        await view.learn_until(self.program.helper(branch),
            lambda source:view.ahead_counter(source,SHORT_POSITION)==(3 if taken else 0),
            'different short record steers the shared early branch base without relearning either original')
        await self.settle()
        return view

    async def short_query(self, path):
        view = await self.select(path.branch)
        source = await view.visit(path)
        self.checks.provider(source,path)
        await self.settle()
        return source


@asynccontextmanager
async def short_context_env(agent, program, coverage,*,checks_factory=ShortContextChecks,
                            binding_factory=history_working_set_binding,env_factory=ShortContextEnv):
    checks = checks_factory(program,coverage)
    phr = BpuPhrChecker(scope='two branch PCs share short history without sharing learning',record_limit=8)
    def bind(agent,**options):
        result=binding_factory(agent,**options)
        if isinstance(result,tuple):
            binding,checks.storage_layout=result
            return binding
        return result
    observation = PipelineObservation(agent,checks,sources=EarlyDirectionSources(),binding_factory=bind)
    checks.pipeline = observation.checker
    try:
        async with observation,agent.observe_phr(phr):
            pc = program.helper(getattr(program,'learning_order',OWNERS)[0]).branch_pc
            await agent.reset(pc)
            source = await agent.next_transaction(start_pc=pc)
            await agent.configure_predictors(ubtb=True,abtb=False,mbtb=True,tage=False,
                sc=False,ittage=False,ras=False,settle=True)
            env = env_factory(agent,observation,source,program,checks)
            yield env
            phr.summary()
    except BaseException as error:
        coverage.evidence = dict(checks.summary(),status='FAIL',first_error_type=type(error).__name__,first_error=str(error))
        raise
    else:
        coverage.evidence = dict(checks.summary(),status='PASS')


async def working_set_direction_boundary(env,path,*,taken):
    """A bounded number of genuine outcomes, not a cycle delay or protection target."""
    view=await env.select(path.branch)
    for _ in range(7+1):
        source=await view.visit(path)
        await env.settle()
        if env.checks.states()[path.ordinal][0]==(7 if taken else 0):
            env.checks.direction_consumer(source,path,taken=taken)
            return
    raise AssertionError('normal original outcomes did not establish the declared direction boundary')


async def working_set_reverse(env,path,*,taken):
    c=env.checks
    await env.settle()
    before=c.states()
    counter,protection=before[path.ordinal]
    plan=env.program.reversal(path,counter=counter,protection=protection,taken=taken)
    c.declare_result(path,taken)
    view=await env.select(path.branch)
    await view.short_guidance(taken=taken)
    for original,old,new in plan:
        start=len(c.learning)
        source=await view.visit(original)
        await env.settle()
        c.changed_by_original(source,original,old,new,start,taken=taken)
    c.check({owner:state for owner,state in before.items() if owner!=path.ordinal},
        {owner:state for owner,state in c.states().items() if owner!=path.ordinal},
        'changing one branch/path preserves all thirteen other direction and protection owners')


async def working_set_consumers(env,phase,positive):
    c=env.checks
    c.phase=phase
    for branch in env.program.learning_order:
        view=await env.select(branch)
        for taken in (False,True):
            paths=[path for path in env.program.paths if path.branch==branch and (path.ordinal in positive)==taken]
            if not paths:continue
            await view.short_guidance(taken=taken)
            for path in paths:
                source=await view.visit(path)
                c.direction_consumer(source,path,taken=taken)
                await env.settle()
