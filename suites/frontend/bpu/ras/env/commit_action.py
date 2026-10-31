"""Existing drivers and native monitors; cases never operate clock edges."""
from copy import deepcopy
import sys
from suites.frontend.bpu.ras.checker.commit_action import CommitActionChecks
from suites.frontend.bpu.ras.model.commit_action import A,B,C
from suites.frontend.bpu.ras.monitor.commit_action import commit_facts
from suites.frontend.bpu.runtime.trace import dump_trace
from suites.frontend.bpu.runtime.artifacts import output_directory
from suites.frontend.bpu.runtime.paths import REPO_ROOT


def export_commit_trace(rows,path,*,primary=None):
    """Use the existing opt-in gzip exporter; never hide a real mismatch."""
    try:
        return dump_trace(path,rows)
    except Exception as error:
        if primary is None:raise
        primary.add_note('optional commit trace export failed: '+repr(error))
        return None


async def run(agent,program,coverage,evidence):
    checks=CommitActionChecks(program)
    rows=[];original=None;saved=None

    check=checks.check

    try:
        await agent.reset()
        for address in (A,B):
            source=deepcopy(agent.snapshot().commit_meta)
            await agent.act(2,start_pc=address-8,position=3)
            await agent.commit(source,action=2)
        coverage.reach('normally-retired-prefix')
        saved=deepcopy(agent.snapshot())
        original=deepcopy(saved.commit_meta)
        await agent.act(2,start_pc=C-8,position=3)
        coverage.reach('genuine-original-source')
        async with agent.observe_committed() as observations:
            try:
                await agent.commit(saved.commit_meta,action=program.action)
            finally:
                rows.extend(dict(tick=item.event.tick,**item.value) for item in observations)
                compact=commit_facts(rows)
                evidence.update(compact)
                payload,registered=compact['actual_input'],compact['actual_registered']
                export_commit_trace(rows,output_directory(REPO_ROOT,'ras')/('commit-action-'+program.label+'.json'),
                                    primary=sys.exception())
                expected=dict(action=program.action,meta=original)
                check(expected,payload,'complete real original commit input')
                coverage.reach('complete-public-input')
                coverage.reach('actual-registered-commit',tick=compact['registered_tick'])
                evidence.update(actual_input=payload,actual_registered=registered,
                    expected_actions=dict(pop=bool(program.action&1),push=bool(program.action&2)),
                    actual_actions=dict(pop=bool(registered['pop']),push=bool(registered['push'])),
                    retained=dict(head=rows[-1]['head'],cells=rows[-1]['cells']))
        actual=rows[-1]
        retained_address=actual['cells'][actual['head']]['address']*2
        check(program.stack[-1],retained_address,'retired program owns its actual retained top, not speculative C')
        coverage.reach('retained-program-effect')
        # Speculative context is deliberately not repaired by this upstream
        # attribute correction. These consumers check preserved older frames;
        # the separate full retained comparison above proves retirement.
        consumers=tuple([(await agent.act(1)).top*2 for _ in (B,A)])
        check((B,A),consumers,'fresh consumers preserve both real older identities')
        coverage.reach('independent-consumers')
        check(original,saved.commit_meta,'original source metadata remains unchanged')
        coverage.reach('immutable-source');coverage.finish()
        evidence.update(status='PASS',consumers=consumers)
    except BaseException as error:
        evidence.update(status='FAIL',error_type=type(error).__name__,error=str(error),
            differences=[dict(path=d.path,expected=repr(d.expected),actual=repr(d.actual))
                         for d in getattr(error,'differences',())[:12]])
        raise
    finally:
        evidence.update(program=program.state(),original_source_unchanged=saved is not None and saved.commit_meta==original,
            reference_failure=None if agent.reference.failure is None else str(agent.reference.failure),
            reference_retirements=agent.reference.model.retirements,
            whole_retained_state_checked_by_existing_reference=True,
            full_FTQ_reachability_proved=False)
