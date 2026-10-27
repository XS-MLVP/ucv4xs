"""Explicitly dropped call-retirement notifications exercise defensive BOS repair.

All pointers come from checked, genuine pre-operation metadata. Actions zero
and three, enable gating, internal state writes and full-FTQ legality are not
part of this fault-injection scenario. Only compact endpoint evidence is saved.
"""
from bpuverify.common.model.configuration import *
from copy import deepcopy
from dataclasses import asdict

from toffee import CheckContext, ClockCycles, Scoreboard, ScoreboardMode
from bpuverify.ras.model.addresses import return_addr
from bpuverify.ras.model.retirement import DistinctSpeculation, Retirement
from bpuverify.ras.scoreboard.retirement import check_observation


async def check_gap(agent, observations, *, epoch, kind):
    if epoch not in ('same', 'cross') or kind not in ('threshold-hold', 'gap-reclaim', 'push-priority'):
        raise ValueError('unsupported retirement-gap semantic context')
    await agent.reset()
    speculation, retired = DistinctSpeculation(), Retirement()
    checks, records = Scoreboard('ras.retirement_gap'), []

    async def operation(action, *, pc=0, retire=True, phase):
        nonlocal speculation, retired
        sequence = len(records) + 1
        before = asdict(agent.snapshot())
        metadata = deepcopy(before['commit_meta'])
        request = dict(epoch=epoch, kind=kind, phase=phase, action=action, pc=pc,
            retire=retire, genuine_commit_meta=metadata)

        def context(event=None, accepted=None):
            return CheckContext(scoreboard='ras.retirement_gap', mode=ScoreboardMode.DIRECT,
                sequence_id=sequence, request=request, accepted_event=accepted, observed_event=event)

        checks.check(expected=speculation.public(retired), actual=before, context=context())
        # Carry genuine metadata only after comparison with input-derived state.
        checks.check(expected=speculation.metadata(), actual=metadata, context=context())
        address = return_addr(pc, 3) if action == 2 else None
        after_speculation = speculation.act(action, retired, address=address)
        after_retired = (retired.accept(action, ssp=speculation.ssp, tosw=speculation.write, address=address)
            if retire else retired)
        first = len(observations)
        speculative = await agent.act(action, start_pc=pc, position=3)
        committed = await agent.commit(metadata, action=action) if retire else None
        # Native BOS is updated after the registered commit; timingTop samples
        # its new range on the following cycle. This protocol drain belongs in
        # the case support, never in the testcase or a falling-edge wait.
        await ClockCycles(agent.dut.clock, 1)
        samples = observations[first:]
        specs = [sample for sample in samples if sample.value['speculative']['valid']]
        commits = [sample for sample in samples if sample.value['commit']['valid']]
        checks.check(expected=1, actual=len(specs), context=context(samples[-1].event))
        checks.check(expected=int(retire), actual=len(commits), context=context(samples[-1].event))
        checks.check(expected=6 if retire else 3, actual=len(samples), context=context(samples[-1].event))
        spec_event = specs[0].event
        commit_event = commits[0].event if retire else None
        checks.check(expected=dict(enable=1, action=action, branch_type=3 if action == 1 else 2,
            position=3, start_pc=pc), actual=specs[0].value['speculative']['bits'], context=context(spec_event))
        if retire:
            checks.check(expected=dict(action=action, branch_type=3 if action == 1 else 2, meta=metadata),
                actual=commits[0].value['commit']['bits'], context=context(commit_event, commit_event))
            checks.check(expected=4, actual=commit_event.tick - spec_event.tick, context=context(commit_event))
        for index, sample in enumerate(samples):
            tick = sample.event.tick
            if index:
                checks.check(expected=2, actual=tick - samples[index - 1].event.tick, context=context(sample.event))
            visible_spec = after_speculation if tick >= spec_event.tick + 2 else speculation
            visible_retired = after_retired if retire and tick >= commit_event.tick + 4 else retired
            top_retired = after_retired if retire and tick >= commit_event.tick + 6 else retired
            pending = (dict(push=int(action == 2), pop=int(action == 1), ssp=metadata['ssp'], tosw=metadata['tosw'])
                if retire and tick == commit_event.tick + 2 else None)
            check_observation(checks, sample, speculation=visible_spec, retired=visible_retired,
                top_retired=top_retired, request=request, sequence=sequence, accepted_event=commit_event, pending=pending)
        checks.check(expected=after_speculation.public(retired), actual=asdict(speculative), context=context(spec_event))
        if retire:
            checks.check(expected=after_speculation.public(after_retired, top_retired=retired),
                actual=asdict(committed), context=context(commit_event, commit_event))
        checks.check(expected=after_speculation.public(after_retired), actual=asdict(agent.snapshot()),
            context=context(samples[-1].event, commit_event))
        record = dict(request=request, distance=(speculation.write - retired.bos) % RAS_POINTER_MODULUS,
            before=retired.native(), after=after_retired.native(), public_after=after_speculation.public(after_retired),
            spec_tick=spec_event.tick, commit_tick=commit_event.tick if retire else None, samples_checked=len(samples))
        records.append(record)
        speculation, retired = after_speculation, after_retired
        return record

    await operation(2, pc=0xA1000000, phase='base-call')
    # A semantic epoch transition, not a physical stack-slot sweep: preserve a
    # base frame while ordinary committed temporary pairs advance the queue.
    for _ in range(4 if epoch == 'same' else RAS_SPEC_ENTRIES - 1):
        await operation(2, pc=0xA2000000, phase='epoch-prefix-call')
        await operation(1, phase='epoch-prefix-return')
    baseline = dict(speculation=speculation.metadata(), retirement=retired.native())
    gap = 2 if kind == 'threshold-hold' else 3
    for index in range(gap - 1):
        await operation(2, pc=0xA3000000 + 0x100 * index, retire=False, phase='omitted-call-retirement')
    target = await operation(2 if kind == 'push-priority' else 1, pc=0xA4000000, phase='gap-boundary')
    checks.check(expected=gap, actual=target['distance'])
    checks.check(expected=int(epoch == 'cross'),
        actual=int(target['request']['genuine_commit_meta']['tosw']['flag'] != target['before']['bos']['flag']))
    if kind == 'gap-reclaim':
        # The dropped frame has no committed address. After defensive reclaim,
        # its speculative entry is no longer live; check retained-cell fallback
        # and one further real return before resuming ordinary retirement.
        await operation(1, phase='fallback-unwind')
    survivor = speculation.public(retired)
    await operation(2, pc=0xA5000000, phase='continued-call')
    await operation(1, phase='continued-return')
    final = speculation.public(retired)
    checks.check(expected={key: survivor['redirect_meta'][key] for key in ('ssp', 'sctr')},
        actual={key: final['redirect_meta'][key] for key in ('ssp', 'sctr')})
    checks.check(expected=survivor['top'], actual=final['top'])
    return dict(epoch=epoch, kind=kind, scope='standalone public-port dropped-call-retirement fault injection; not normal FTQ legality',
        omitted_call_retirements=gap - 1, baseline=baseline, target=target,
        operations_checked=len(records), cycles_checked=sum(row['samples_checked'] for row in records),
        final_public=final, final_retirement=retired.native(), checks=asdict(checks.status))
