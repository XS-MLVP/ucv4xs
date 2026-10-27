"""Check complete retained committed cells every cycle using public operations."""
from bpuverify.common.model.configuration import *
from copy import deepcopy
from dataclasses import asdict

from toffee import CheckContext
from toffee import Scoreboard
from toffee import ScoreboardMode
from bpuverify.ras.model.addresses import return_addr
from bpuverify.ras.model.model import CommittedStack
from bpuverify.ras.model.model import advance


def projection(state):
    return dict(top=state['top'], ssp=state['redirect_meta']['ssp'], sctr=state['redirect_meta']['sctr'])


async def check_case(agent, observations, *, slot, mode):
    if type(slot) is not int or slot not in range(RAS_GROUPS) or mode not in ('normal', 'saturated'):
        raise ValueError('indexed scope is configured SSP slots times normal/saturated')
    await agent.reset()
    reference, checks, records = CommittedStack(), Scoreboard('ras.committed_cells'), []

    async def operation(action, *, pc=0, position=0, phase):
        nonlocal reference
        before = asdict(agent.snapshot())
        metadata = deepcopy(before['commit_meta'])
        request = dict(slot=slot, mode=mode, phase=phase, action=action, pc=pc, position=position,
            genuine_commit_meta=metadata)
        initial_context = CheckContext(scoreboard='ras.committed_cells', mode=ScoreboardMode.DIRECT,
            sequence_id=len(records) + 1, request=request,
            observed_event=observations[-1].event if observations else None)
        checks.check(expected=reference.projection(), actual=projection(before), context=initial_context)
        checks.check(expected=reference.head, actual=before['commit_meta']['ssp'], context=initial_context)
        following = advance(reference, action, address=return_addr(pc, position) if action == 2 else None)
        expected_before, expected_after = reference.native(), following.native()
        expected_projection_before, expected_projection_after = reference.projection(), following.projection()
        expected_spec = dict(enable=1, action=action, branch_type=3 if action == 1 else 2,
            position=position, start_pc=pc)
        expected_commit = dict(action=action, branch_type=3 if action == 1 else 2, meta=metadata)
        first = len(observations)
        speculative = await agent.act(action, start_pc=pc, position=position)
        committed = await agent.commit(metadata, action=action)
        samples = observations[first:]
        accepted = [sample for sample in samples if sample.value['commit']['valid']]
        specs = [sample for sample in samples if sample.value['speculative']['valid']]
        completion_context = CheckContext(scoreboard='ras.committed_cells', mode=ScoreboardMode.DIRECT,
            sequence_id=len(records) + 1, request=request,
            accepted_event=accepted[0].event if accepted else None,
            observed_event=samples[-1].event if samples else initial_context.observed_event)
        checks.check(expected=1, actual=len(accepted), context=completion_context)
        checks.check(expected=1, actual=len(specs), context=completion_context)
        accepted_event, spec_event = accepted[0].event, specs[0].event
        context = lambda event: CheckContext(scoreboard='ras.committed_cells', mode=ScoreboardMode.DIRECT,
            sequence_id=len(records) + 1, request=request, accepted_event=accepted_event, observed_event=event)
        checks.check(expected=expected_spec, actual=specs[0].value['speculative']['bits'], context=context(spec_event))
        checks.check(expected=expected_commit, actual=accepted[0].value['commit']['bits'], context=context(accepted_event))
        checks.check(expected=4, actual=accepted_event.tick - spec_event.tick, context=context(accepted_event))
        checks.check(expected=5, actual=len(samples), context=context(samples[-1].event))
        for sample in samples:
            row, tick = sample.value, sample.event.tick
            checks.check(expected=dict(reset=0, enable=1, redirect_valid=0),
                actual=dict(reset=row['reset'], enable=row['enable'], redirect_valid=row['redirect']['valid']), context=context(sample.event))
            checks.check(expected=int(tick == accepted_event.tick + 2), actual=row['pending_commit']['valid'], context=context(sample.event))
            if row['pending_commit']['valid']:
                pending = row['pending_commit']
                checks.check(expected=dict(push=int(action == 2), pop=int(action == 1),
                    ssp=metadata['ssp'], tosw=metadata['tosw']),
                    actual={key: pending[key] for key in ('push', 'pop', 'ssp', 'tosw')}, context=context(sample.event))
            # Public inputs use rise-write; the parent register and child state
            # update follow on two distinct cycles. Keep that inside this helper.
            checks.check(expected=expected_after if tick >= accepted_event.tick + 4 else expected_before,
                actual=dict(head=row['head'], cells=list(row['cells'])), context=context(sample.event))
            checks.check(expected=expected_projection_after if tick >= spec_event.tick + 2 else expected_projection_before,
                actual=projection(row['public']), context=context(sample.event))
        checks.check(expected=following.projection(), actual=projection(asdict(speculative)), context=context(samples[-1].event))
        checks.check(expected=following.projection(), actual=projection(asdict(committed)), context=context(samples[-1].event))
        records.append(dict(request=request, accepted_tick=accepted_event.tick,
            spec_tick=spec_event.tick, expected_before=expected_before, expected_after=expected_after,
            expected_projection_before=expected_projection_before, expected_projection_after=expected_projection_after,
            cycles=[dict(tick=sample.event.tick, **sample.value) for sample in samples]))
        reference = following

    for index in range((slot - 1) % RAS_GROUPS):
        await operation(2, pc=0x92000000 + 0x40 * index, position=index % 8 + 1, phase='prefix')
    repetitions = 3 if mode == 'normal' else 9
    for index in range(repetitions):
        await operation(2, pc=0x94000000 + 0x100 * slot, position=3, phase='repeat_push')
        if index == 0:
            checks.check(expected=slot, actual=reference.head)
    before_reuse = reference.projection()
    for index in range(RAS_SPEC_ENTRIES + 8):
        await operation(2, pc=0x96000000 + 0x40 * index, position=index % 8 + 1, phase='queue_reuse_push')
        await operation(1, phase='queue_reuse_pop')
        checks.check(expected=before_reuse, actual=reference.projection())
    for _ in range(repetitions):
        await operation(1, phase='repeat_pop')
    while len(reference.groups) > 1:
        await operation(1, phase='neighbor_unwind')
    return dict(slot=slot, mode=mode, records=records, cycles_checked=sum(len(row['cycles']) for row in records),
        capacity_evictions=[asdict(group) for group in reference.evicted],
        final_projection=reference.projection(), final_native=reference.native(), checks=asdict(checks.status))
