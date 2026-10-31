"""Compare complete public state and retained committed storage at one event."""
from toffee import CheckContext, ScoreboardMode


def check_observation(checks, sample, *, speculation, retired, top_retired=None, request, sequence,
        accepted_event=None, pending=None):
    context = CheckContext(scoreboard='ras.retirement_gap', mode=ScoreboardMode.DIRECT,
        sequence_id=sequence, request=request, accepted_event=accepted_event, observed_event=sample.event)
    row = sample.value
    checks.check(expected=dict(reset=0, enable=1, redirect_valid=0),
        actual=dict(reset=row['reset'], enable=row['enable'], redirect_valid=row['redirect']['valid']), context=context)
    checks.check(expected=retired.native(),
        actual=dict(head=row['head'], cells=list(row['cells']), bos=row['bos']), context=context)
    checks.check(expected=speculation.public(retired, top_retired=top_retired), actual=row['public'], context=context)
    checks.check(expected=int(pending is not None), actual=row['pending_commit']['valid'], context=context)
    if pending is not None:
        checks.check(expected=pending, actual={key: row['pending_commit'][key] for key in pending}, context=context)
