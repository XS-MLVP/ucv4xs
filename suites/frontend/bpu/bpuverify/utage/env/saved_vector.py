"""Normal preparation, saved-vector recovery and all fresh consumers."""
from copy import deepcopy
from bpuverify.utage.transaction.types import UtageBaseBranch,UtageTraining
from bpuverify.utage.checker.saved_vector import Checks
from bpuverify.utage.driver.saved_vector import SavedVectorDriver
from bpuverify.utage.monitor.saved_vector import Monitor


async def run(agent,program,coverage,evidence):
    await agent.reset()
    checks=Checks(program)
    monitor=Monitor(agent).start()
    accepted=agent.reference.model.accepted_feedback
    primary=None

    async def obtain(profile,state,seed=None):
        positions=program.positions(seed)
        branches=tuple(None if p is None else UtageBaseBranch(p,int(p==2)) for p in positions)
        handle=agent.submit_predict_branches(profile.pc,branches,folded_history=profile.history)
        source=await handle
        token=checks.query(profile,handle,source,state,positions)
        return token,source

    def feedback(profile,original,position,taken,error):
        token,source=original
        tx=UtageTraining(profile.pc,position,taken,deepcopy(source.meta),mispredict=int(error))
        checks.original_feedback(token,tx)
        return tx

    try:
        for profile in program.profiles:
            for step in profile.setup:
                original=await obtain(profile,step.sources,step.seed_position)
                await agent.train(feedback(profile,original,step.position,step.taken,step.error))
                checks.learning(profile,step)
                checks.native(monitor)
                await obtain(profile,step.after)
        coverage.reach('normally-learned-three-vectors')
        counts=[tuple(v.counter for v in p.prepared) for p in program.profiles]
        checks.check(3,len(set(counts)),'all three full vectors discriminate original ages')
        checks.check(True,all(len({v[t] for v in counts})==3 for t in (0,1)),'both short and long providers discriminate all three ages')
        coverage.reach('both-providers-discriminate-ages')
        original=await obtain(program.target,program.target.prepared)
        await obtain(program.decoy,program.decoy.prepared)
        tx=feedback(program.target,original,15,0,True) if program.learning else None
        monitor.arm_window()
        transfers=await SavedVectorDriver(agent).send(program,tx)
        if program.learning:checks.learning(program.target)
        checks.native(monitor)
        checks.recovery(monitor.recovery_rows(program.stage),transfers,monitor)
        for rule in program.rules[2:9]:coverage.reach(rule)
        for profile in program.profiles:
            await obtain(profile,program.latest if profile.name==program.target.name else profile.prepared)
        checks.native(monitor)
        checks.check(program.feedbacks,agent.reference.model.accepted_feedback-accepted,'every normal original feedback accepted exactly once')
        checks.check((int(program.learning),)*2,(agent.reference.model.low_tick,agent.reference.model.high_tick),'only declared protected allocation failure; no hidden aging')
        checks.finish(monitor)
        agent.reference.raise_failure()
        coverage.reach('fresh-three-vector-consumers')
        coverage.reach('immutable-originals')
    except BaseException as error:
        primary=error
        evidence.update(checks.snapshot(),status='FAIL',error_type=type(error).__name__,error=str(error)[:6000],
            actual_native_writes=monitor.native_updates,actual_feedbacks=monitor.public)
        raise
    finally:
        try: await monitor.aclose()
        except BaseException as error:
            if primary is None:
                evidence.update(checks.snapshot(),status='FAIL',error_type=type(error).__name__,error=str(error)[:6000])
                raise
            primary.add_note(f'saved-vector cleanup: {error!r}')
    # A teardown error cannot leave checked credit for an incomplete scope.
    coverage.finish()
    evidence.update(checks.snapshot(),status='PASS',completed=list(program.rules),
        actual_native_writes=monitor.native_updates,actual_feedbacks=monitor.public,
        all_protection_cells_compared=1024)
