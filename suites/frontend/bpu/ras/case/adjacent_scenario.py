"""Adjacent logical operations through the existing public PulseDriver."""
from dataclasses import asdict
from toffee import CheckContext
from toffee import Scoreboard
from toffee import ScoreboardMode
from suites.frontend.bpu.ras.model.addresses import return_addr
from suites.frontend.bpu.ras.model.model import CommittedStack
from suites.frontend.bpu.ras.model.model import advance
from suites.frontend.bpu.ras.transaction.types import RasOperation


def project(value):
    return dict(top=value['top'], ssp=value['redirect_meta']['ssp'], sctr=value['redirect_meta']['sctr'])


async def check_burst(agent, observations, operations, *, label):
    await agent.reset()
    reference, expected, frames = CommittedStack(), [], []
    for request in operations:
        action, pc, position = request['action'], request.get('pc', 0), request.get('position', 0)
        if action not in (1, 2):
            raise ValueError('adjacent bypass scope is ordinary call/return only')
        reference = advance(reference, action, address=return_addr(pc, position) if action == 2 else None)
        expected.append(reference.projection())
        frames.append(dict(action=action, position=position, start_pc=pc))
    first = len(observations)
    # PulseDriver already guarantees adjacent payload launches and the final
    # drain. Expose a burst operation, not an event loop or edge to testcase.
    actuals = await agent.act_many(tuple(RasOperation(request['action'],
        start_pc=request.get('pc', 0), position=request.get('position', 0)) for request in operations))
    event = observations[-1].event
    samples = observations[first:]
    checks = Scoreboard('ras.adjacent_push_pop')
    context = CheckContext(scoreboard='ras.adjacent_push_pop', mode=ScoreboardMode.DIRECT,
        sequence_id=1, request=dict(label=label, operations=operations), observed_event=event)
    checks.check(expected=len(operations) + 1, actual=len(samples), context=context)
    accepted = [sample for sample in samples if sample.value['speculative']['valid']]
    checks.check(expected=len(operations), actual=len(accepted), context=context)
    checks.check(expected=frames, actual=[sample.value['speculative']['bits'] for sample in accepted], context=context)
    checks.check(expected=expected, actual=[project(asdict(actual)) for actual in actuals], context=context)
    for index, sample in enumerate(samples):
        current = CheckContext(scoreboard='ras.adjacent_push_pop', mode=ScoreboardMode.DIRECT,
            sequence_id=index + 1, request=dict(label=label, operations=operations),
            accepted_event=accepted[max(0, index - 1)].event, observed_event=sample.event)
        checks.check(expected=0, actual=sample.value['reset'], context=current)
        checks.check(expected=0, actual=sample.value['commit']['valid'], context=current)
        checks.check(expected=0, actual=sample.value['redirect']['valid'], context=current)
        checks.check(expected=CommittedStack().native(),
            actual=dict(head=sample.value['head'], cells=list(sample.value['cells'])), context=current)
        checks.check(expected=CommittedStack().projection() if index == 0 else expected[index - 1],
            actual=project(sample.value['public']), context=current)
        if index:
            checks.check(expected=2, actual=sample.event.tick - samples[index - 1].event.tick, context=current)
    checks.check(expected=reference.projection(), actual=project(asdict(agent.snapshot())), context=context)
    return dict(label=label, operations=operations, expected=expected,
        accepted_ticks=[sample.event.tick for sample in accepted],
        cycles=[dict(tick=sample.event.tick, **sample.value) for sample in samples],
        final=asdict(agent.snapshot()), checks=asdict(checks.status))
