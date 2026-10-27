"""Normal driver/monitor flow; no production imports or SDK are patched."""
from copy import deepcopy

from bpuverify.bpu.env.main_service import MainService, branch, main_program
from bpuverify.bpu.model.main_sources import source_entries
from bpuverify.bpu.model.main_service import observed_counter
from bpuverify.bpu.transaction.types import BpuBatchTraining
from bpuverify.bpu.checker.main_sibling import MainSiblingChecks
from bpuverify.bpu.env.main_sibling import release
from bpuverify.bpu.model.main_dynamic_target import (
    PC, STREAM_PC, EARLIER, LATER, FALLBACK, LATER_TARGET, VERSIONS,
    qualified_feedback)


async def prepare(env, setup):
    async def resolve(source, *outcomes):
        token = env.checker.source_token(source)
        branches = qualified_feedback(token.middle.branch, tuple(outcomes))
        setup.append(dict(source_id=token.sequence, pc=token.pc,
            branches=[dict(position=b.position, kind=b.branch_type, taken=b.taken,
                           target=b.target, mispredict=b.mispredict) for b in branches]))
        await env.resolve(source, *branches)

    loop = await env.capture_source(STREAM_PC)
    await resolve(loop, branch(FALLBACK, STREAM_PC, 2))
    cold = await env.capture_source(PC)
    # Offset fetch really excludes the earlier instruction. The conditional
    # branch is therefore executed when its independent direction is trained.
    source = await env.capture_source(PC + EARLIER + 1)
    await resolve(source, branch(LATER, LATER_TARGET, 1))
    for _ in range(3):  # Weak-T -> NT -> strong-NT -> an actual hold.
        source = await env.capture_source(PC + EARLIER + 1)
        await resolve(source, branch(LATER, LATER_TARGET, 1, taken=False),
                      branch(FALLBACK, STREAM_PC, 3))
    source = await env.capture_source(PC)
    await resolve(source, branch(EARLIER, VERSIONS[0], 3))
    current = tuple([await env.capture_source(PC) for _ in range(2)])
    return cold, current


async def submit(env, observer, source, version):
    token = env.checker.source_token(source)
    before = env.checker.last_tick
    branches = qualified_feedback(token.middle.branch,
        (branch(EARLIER, VERSIONS[version], 3),))
    observer.check((3, 1, 1), (branches[0].branch_type, branches[0].taken,
        branches[0].mispredict), 'same indirect instruction changes its dynamic target')
    tx = BpuBatchTraining(PC, source.meta.resolve, branches)
    env.checker.plan_feedback(source, tx)
    event = await env.agent.training_driver.send(tx)
    def mature(checker):
        observer.raise_failure()
        receipts = tuple((tick, resolution) for tick, resolution in
            checker.resolutions_for_source(source) if tick > before)
        main = checker.model.sources.main
        return bool(receipts) and main.offered is None and not any(main.entry_offers.values())
    await env.observation.wait('same-indirect-original-version-mature', mature)
    accepted, = [(tick, resolution) for tick, resolution in
        env.checker.resolutions_for_source(source) if tick > before]
    observer.check((event.tick, True), (accepted[0], accepted[1].origin is token),
                   'accepted feedback has the exact original occurrence')
    observer.accepted.append(dict(version=version, source_id=token.sequence, tick=event.tick))
    observer.check(version, len(observer.incoming), 'all complete target proposals were observed')
    observer.check(observer.program.effect(version), observer.incoming[-1]['bits'],
                   'only the earlier indirect target changes')


async def check_with_agent(agent, program, evidence, coverage):
    observer = None
    try:
        async with main_program(agent) as env:
            setup = []
            evidence['setup'] = setup
            cold, current = await prepare(env, setup)
            observer = MainSiblingChecks(env, program)
            for source in (cold, *current):
                token = env.checker.source_token(source)
                observer.snapshots.append((source, deepcopy(source.meta.resolve), deepcopy(source.meta.redirect)))
                entries = tuple((way, entry.position, entry.kind, entry.counter)
                    for way, entry in enumerate(source_entries(token.lookup)[0]) if entry.hit)
                observer.check(() if source is cold else ((0, EARLIER, 3, 2), (1, LATER, 1, 0)),
                    entries, 'indirect source and strong-NT sibling have independently learned identities')
            observer.check(3, len({env.checker.source_token(source).sequence for source in (cold, *current)}),
                           'three different original occurrences')
            coverage.reached('qualified-original-source')
            coverage.reached('strong-unexecuted-sibling', counter=0)
            async with MainService(env, observer) as service:
                await service.start()
                await submit(env, observer, current[0], 1)
                observer.check((0, 0, 0), tuple(map(len, observer.written)),
                               'actual read priority prevents the first version from committing')
                coverage.reached('actual-read-blocked-learning')
                if program.phase == 'committed':
                    await release(env, service, observer, entry_count=1, direction_count=1)
                    await service.start()
                observer.check(0 if program.phase == 'pending' else 1,
                    sum(len(port) for port in observer.written[:2]), 'actual declared version visibility')
                coverage.reached('declared-version-visibility', phase=program.phase)
                await submit(env, observer, cold if program.origin == 'old-cold' else current[1], 2)
                await release(env, service, observer,
                    entry_count=1 if program.phase == 'pending' else 2, direction_count=2)
                expected = [program.effect(2)] if program.phase == 'pending' else [program.effect(1), program.effect(2)]
                observer.check((expected, []), tuple([row['bits'] for row in port] for port in observer.written[:2]),
                               'latest complete target remains with the earlier indirect instruction')
                coverage.reached('complete-latest-entry-service')
                sibling = await env.capture_source(PC + EARLIER + 1)
                token = env.checker.source_token(sibling)
                later = tuple(entry for row in source_entries(token.lookup) for entry in row
                              if entry.hit and entry.position == LATER and entry.kind == 1)
                observer.check((1, 0), (len(later), later[0].counter if later else None),
                               'unexecuted conditional retains its independently learned strong-NT direction')
                observer.check((FALLBACK, STREAM_PC, 3),
                    (token.middle.branch.position, token.middle.branch.target, int(token.middle.branch.kind)),
                    'fresh offset prediction skips the unexecuted conditional sibling')
                observer.consumers.append(dict(pc=token.pc, verified_middle_position=token.middle.branch.position,
                    verified_middle_target=token.middle.branch.target, later_counter=later[0].counter))
                coverage.reached('unexecuted-sibling-consumer', query_tick=sibling.prediction_tick)
                earlier = await env.capture_source(PC)
                token = env.checker.source_token(earlier)
                observer.check((EARLIER, VERSIONS[2], 3),
                    (token.middle.branch.position, token.middle.branch.target, int(token.middle.branch.kind)),
                    'fresh indirect consumer follows its newest dynamic target')
                wanted = program.direction()
                observer.check([wanted, wanted], [observed_counter(row['bits']) for row in observer.written[2]],
                               'both services preserve the direction of the unexecuted conditional')
                coverage.reached('latest-earlier-consumer', query_tick=earlier.prediction_tick)
                observer.check(True, observer.summary()['immutable_originals'], 'original sources were not patched')
                coverage.reached('immutable-originals')
                observer.status = 'PASS'
    except BaseException as error:
        evidence.update({} if observer is None else observer.summary())
        evidence.update(status='FAIL', first_error_type=type(error).__name__, first_error=str(error))
        if getattr(error, 'differences', None):
            evidence['differences'] = [dict(path=str(item.path), expected=str(item.expected), actual=str(item.actual))
                                       for item in error.differences]
        raise
    else:
        coverage.finish()
        evidence.update(observer.summary())
