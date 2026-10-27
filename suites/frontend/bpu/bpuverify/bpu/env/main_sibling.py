"""Real old/current sources cross pending/committed visibility in one DUT."""
from copy import deepcopy

from bpuverify.bpu.env.main_service import MainService, branch, main_program
from bpuverify.bpu.model.main_sources import source_entries
from bpuverify.bpu.model.main_service import observed_counter
from bpuverify.bpu.transaction.types import BpuBatchTraining
from bpuverify.bpu.model.main_sibling import (
    PC, STREAM_PC, EARLIER, LATER, FALLBACK, LATER_TARGET, VERSIONS)
from bpuverify.bpu.checker.main_sibling import MainSiblingChecks


async def prepare(env):
    loop = await env.capture_source(STREAM_PC)
    await env.resolve(loop,branch(FALLBACK,STREAM_PC,2,wrong=True))
    cold = await env.capture_source(PC)
    source = await env.capture_source(PC)  # A different genuinely cold occurrence.
    await env.resolve(source,branch(LATER,LATER_TARGET,1,wrong=True))
    for _ in range(3):  # Two-bit weak-T -> NT -> strong-NT, then a real hold.
        source = await env.capture_source(PC)
        await env.resolve(source,branch(LATER,LATER_TARGET,1,taken=False,wrong=True))
    source = await env.capture_source(PC)
    await env.resolve(source,branch(EARLIER,VERSIONS[0],1,wrong=True))
    for _ in range(3):
        source = await env.capture_source(PC)
        await env.resolve(source,branch(EARLIER,VERSIONS[0],1,taken=False,wrong=True))
    source = await env.capture_source(PC)
    await env.resolve(source,branch(FALLBACK,STREAM_PC,3,wrong=True))
    current = tuple([await env.capture_source(PC) for _ in range(2)])
    return cold,current


async def submit(env, observer, source, version):
    token = env.checker.source_token(source)
    before = env.checker.last_tick
    tx = BpuBatchTraining(PC,source.meta.resolve,(branch(EARLIER,VERSIONS[version],3,wrong=True),))
    env.checker.plan_feedback(source,tx)
    handle = env.agent.training_driver.send(tx)
    event = await handle
    def mature(checker):
        observer.raise_failure()
        receipts = tuple((tick,resolution) for tick,resolution in checker.resolutions_for_source(source) if tick>before)
        main = checker.model.sources.main
        return bool(receipts) and main.offered is None and not any(main.entry_offers.values())
    await env.observation.wait('original-main-version-mature',mature)
    accepted, = [(tick,resolution) for tick,resolution in env.checker.resolutions_for_source(source) if tick>before]
    observer.check((event.tick,True),(accepted[0],accepted[1].origin is token),
                   'driver and actual input have the same original occurrence')
    observer.accepted.append(dict(version=version,source_id=token.sequence,tick=event.tick))
    observer.check(version,len(observer.incoming),'all declared full proposals reached the passive monitor')
    observer.check(observer.program.effect(version),observer.incoming[-1]['bits'],
                   'complete type and cross-region target correction belongs to the earlier branch')


async def release(env, service, observer, *, entry_count, direction_count):
    observer.held = False
    await env.pause()
    def complete(_):
        observer.raise_failure()
        return sum(len(port) for port in observer.written[:2])>=entry_count and len(observer.written[2])>=direction_count
    await env.observation.wait('all-original-main-services-observed',complete)


async def check_with_agent(agent, program, evidence, coverage):
    observer = None
    try:
        async with main_program(agent) as env:
            cold,current = await prepare(env)
            observer = MainSiblingChecks(env,program)
            for source in (cold,*current):
                token = env.checker.source_token(source)
                observer.snapshots.append((source,deepcopy(source.meta.resolve),deepcopy(source.meta.redirect)))
                entries = tuple((way,entry.position,entry.kind,entry.counter) for way,entry in enumerate(source_entries(token.lookup)[0]) if entry.hit)
                observer.check(() if source is cold else ((0,EARLIER,1,0),(1,LATER,1,0)),entries,
                               'the old cold occurrence and both current occurrences are real, distinguishable originals')
            observer.check(3,len({env.checker.source_token(source).sequence for source in (cold,*current)}),
                           'three different real original occurrences, not one reused metadata object')
            coverage.reached('qualified-original-source')
            coverage.reached('strong-unexecuted-sibling',counter=0)
            async with MainService(env,observer) as service:
                await service.start()
                await submit(env,observer,current[0],1)
                observer.check((0,0,0),tuple(map(len,observer.written)),
                               'first new version has not committed under real read priority')
                coverage.reached('actual-read-blocked-learning')
                if program.phase=='committed':
                    await release(env,service,observer,entry_count=1,direction_count=1)
                    await service.start()
                observer.check(0 if program.phase=='pending' else 1,
                    sum(len(port) for port in observer.written[:2]),'declared pending/committed visibility is actual')
                coverage.reached('declared-version-visibility',phase=program.phase)
                source = cold if program.origin=='old-cold' else current[1]
                await submit(env,observer,source,2)
                await release(env,service,observer,
                    entry_count=1 if program.phase=='pending' else 2,direction_count=2)
                expected = [program.effect(2)] if program.phase=='pending' else [program.effect(1),program.effect(2)]
                observer.check((expected,[]),tuple([row['bits'] for row in port] for port in observer.written[:2]),
                               'all actual complete entry services retain the original earlier branch owner')
                coverage.reached('complete-latest-entry-service')
                # Query the not-executed conditional sibling FIRST. A wrong
                # reset then changes a real S2 choice, not merely a counter.
                sibling = await env.capture_source(PC+EARLIER+1)
                token = env.checker.source_token(sibling)
                later = tuple(entry for row in source_entries(token.lookup) for entry in row
                              if entry.hit and entry.position==LATER and entry.kind==1)
                observer.check((1,0),(len(later),later[0].counter if later else None),
                               'an unexecuted later conditional retains strong not-taken')
                # CFI position is relative to the aligned fetch window, not
                # the offset start PC. Frame.values and the existing sibling
                # tests use this same public contract.
                observer.check((FALLBACK,STREAM_PC,3),
                    (token.middle.branch.position,token.middle.branch.target,int(token.middle.branch.kind)),
                    'fresh offset fetch follows real fallback, not the unexecuted sibling target')
                observer.consumers.append(dict(pc=token.pc,verified_middle_position=token.middle.branch.position,
                    verified_middle_target=token.middle.branch.target,later_counter=later[0].counter))
                coverage.reached('unexecuted-sibling-consumer',query_tick=sibling.prediction_tick)
                earlier = await env.capture_source(PC)
                token = env.checker.source_token(earlier)
                observer.check((EARLIER,VERSIONS[2],3),(token.middle.branch.position,token.middle.branch.target,int(token.middle.branch.kind)),
                               'fresh earlier consumer owns the newest complete version')
                expected_direction = program.direction()
                observer.check([expected_direction,expected_direction],[observed_counter(row['bits']) for row in observer.written[2]],
                               'both independent direction services belong to the earlier branch, not its unexecuted sibling')
                coverage.reached('latest-earlier-consumer',query_tick=earlier.prediction_tick)
                observer.check(True,observer.summary()['immutable_originals'],'original metadata was never patched')
                coverage.reached('immutable-originals')
                observer.status='PASS'
    except BaseException as error:
        evidence.update({} if observer is None else observer.summary())
        evidence.update(status='FAIL',first_error_type=type(error).__name__,first_error=str(error))
        if getattr(error,'differences',None):
            evidence['differences']=[dict(path=str(item.path),expected=str(item.expected),actual=str(item.actual)) for item in error.differences]
        raise
    else:
        coverage.finish()  # Includes both passive scopes and the PHR summary.
        evidence.update(observer.summary())
