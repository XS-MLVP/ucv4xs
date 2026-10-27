"""Frozen logical checkpoint and actual metadata; restore/redo plus unwind."""
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


def guarded_return(pc):
    # Independent byte-address arithmetic for Pc.signGuard + 2, not the driver
    # encoder and not any observed output or metadata field.
    signed = pc if pc < (1 << 49) else pc - (1 << 50)
    return ((signed + 2) % (1 << 51)) // 2


async def check_redirect(agent, observations, *, storage, counter, redo):
    await agent.reset()
    label = f'{storage}-counter{counter}-{redo}'
    reference = committed = CommittedStack()
    checks, records = Scoreboard('ras.redirect_redo'), []

    def compare(expected, actual, request):
        checks.check(expected=expected, actual=actual, context=CheckContext(
            scoreboard='ras.redirect_redo', mode=ScoreboardMode.DIRECT,
            sequence_id=len(records) + 1, request=dict(label=label, **request),
            observed_event=observations[-1].event))

    async def speculate(request):
        nonlocal reference
        before = reference
        reference = advance(before, request['action'], address=return_addr(request['pc'], request['position'])
            if request['action'] == 2 else None)
        metadata = deepcopy(agent.snapshot().commit_meta)
        first = len(observations)
        snapshot = await agent.act(request['action'], start_pc=request['pc'], position=request['position'])
        compare(reference.projection(), projection(asdict(snapshot)), request)
        compare(committed.native(), dict(head=observations[-1].value['head'],
            cells=list(observations[-1].value['cells'])), request)
        records.append(dict(kind='speculate', request=request, genuine_meta=metadata,
            expected_before=before.projection(), expected_after=reference.projection(),
            cycles=[dict(tick=row.event.tick, **row.value) for row in observations[first:]]))
        return metadata

    prefix = [dict(action=2, pc=0x98010000, position=3) for _ in range(3)]
    prefix += [dict(action=2, pc=0x98020000, position=5) for _ in range(counter + 1)]
    for request in prefix:
        metadata = await speculate(request)
        if storage == 'committed':
            committed = advance(committed, 2, address=return_addr(request['pc'], request['position']))
            first = len(observations)
            snapshot = await agent.commit(metadata, action=2)
            compare(reference.projection(), projection(asdict(snapshot)), request)
            compare(committed.native(), dict(head=observations[-1].value['head'],
                cells=list(observations[-1].value['cells'])), request)
            records.append(dict(kind='commit', request=request, genuine_meta=metadata,
                expected_committed=committed.native(),
                cycles=[dict(tick=row.event.tick, **row.value) for row in observations[first:]]))
    checkpoint = reference
    metadata = deepcopy(agent.snapshot().redirect_meta)
    # Wrong-path calls are real speculative transactions, never retired, and
    # their metadata is not substituted for the checkpoint.
    for index in range(2):
        await speculate(dict(action=2, pc=0x98030000 + index * 0x40, position=1))
    wrong_projection = reference.projection()
    if redo == 'return':
        action, pc = 1, 0
        expected = advance(checkpoint, 1)
    else:
        action = 2
        pc = {'call-same': 2 * return_addr(0x98020000, 5) - 2,
            'call-distinct-positive': 0x9804800E,
            'call-distinct-negative': (1 << 50) - 0x4012}[redo]
        expected = advance(checkpoint, 2, address=guarded_return(pc))
    frozen = expected.projection()
    first = len(observations)
    snapshot = await agent.recover(metadata, action=action, cfi_pc=pc)
    samples = observations[first:]
    request = dict(action=action, cfi_pc=pc, genuine_redirect_meta=metadata, redo=redo)
    compare(3, len(samples), request)
    payload = dict(action=action, branch_type=3 if action == 1 else 2, meta=metadata, cfi_pc=pc // 2)
    for index, sample in enumerate(samples):
        row = sample.value
        compare(0, row['reset'], request)
        compare(0, row['speculative']['valid'], request)
        compare(0, row['commit']['valid'], request)
        compare(int(index == 0), row['redirect']['valid'], request)
        if index == 0:
            compare(payload, row['redirect']['bits'], request)
        compare(committed.native(), dict(head=row['head'], cells=list(row['cells'])), request)
        compare(wrong_projection if index < 2 else frozen, projection(row['public']), request)
    compare(frozen, projection(asdict(snapshot)), request)
    records.append(dict(kind='recover', request=request, expected_after=frozen,
        wrong_projection=wrong_projection, expected_committed=committed.native(),
        cycles=[dict(tick=row.event.tick, **row.value) for row in samples]))
    reference = expected
    while len(reference.groups) > 1 or reference.groups[-1].counter:
        await speculate(dict(action=1, pc=0, position=0))
    compare(CommittedStack().projection(), projection(asdict(agent.snapshot())), dict(phase='complete-unwind'))
    return dict(label=label, storage=storage, counter=counter, redo=redo, records=records,
        final=asdict(agent.snapshot()), comparisons=asdict(checks.status))
