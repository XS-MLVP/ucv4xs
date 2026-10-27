"""Audit completed transfers; association remains owned by toffee Scoreboard."""
from copy import deepcopy

from toffee import CheckContext, Scoreboard, ScoreboardMode, TransferState


def check_owned_stream(transfers, originals, *, strict_overlap):
    """No second matcher, expected model, pin sampler, or latency constant."""
    board = Scoreboard('predictor.original-request-lifetime')
    board.check(expected=len(originals), actual=len(transfers))
    board.check(expected=True, actual=len(transfers) > 1)
    seen = set()
    receipts = []
    previous = None
    for transfer, original in zip(transfers, originals, strict=True):
        context = CheckContext(board.name, ScoreboardMode.DIRECT,
            sequence_id=transfer.sequence_id, request=original,
            accepted_event=transfer.accepted_event, observed_event=transfer.completed_event)
        def check(expected, actual):
            board.check(expected=expected, actual=actual, context=context)
        check(TransferState.COMPLETED, transfer.state)
        check(False, transfer.sequence_id in seen)
        check(original, transfer.request)
        check(True, callable(transfer.expected))
        check(True, transfer.accepted_event is not None and transfer.completed_event is not None)
        accepted, completed = transfer.accepted_event.tick, transfer.completed_event.tick
        check(True, accepted < completed)
        if previous is not None:
            before_accept, before_complete = previous
            check(True, before_accept < accepted and before_complete < completed)
            check(True, accepted < before_complete if strict_overlap else accepted <= before_complete)
        previous = accepted, completed
        seen.add(transfer.sequence_id)
        receipts.append(dict(source_id=transfer.sequence_id, request=deepcopy(original),
                             accepted_tick=accepted, completed_tick=completed))
    return receipts


def check_batch_completed(before, after, count):
    """Use the real response owner's accounting, not synthetic observations."""
    board = Scoreboard('predictor.original-request-completion')
    board.check(expected=dict(submitted=count, accepted=count, checked=count, completed=count),
        actual={key:getattr(after, key) - getattr(before, key)
                for key in ('submitted', 'accepted', 'checked', 'completed')})
    board.check(expected=dict(failed=0, pending=0, processing=0,
                              unmatched_requests=0, unmatched_observations=0),
        actual={key:getattr(after, key) for key in (
            'failed', 'pending', 'processing', 'unmatched_requests', 'unmatched_observations')})
