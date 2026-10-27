"""Check staged lookup bursts through the existing bound Scoreboard."""
from toffee import TransferState


async def check_lookup_burst(run, expectations):
    expectations = tuple(expectations)
    run.check(True, bool(expectations), point='nonempty staged lookup burst')
    transfers = []
    for profile, base, expected in expectations:
        # Bind each input now: callbacks execute later, after submission.
        def compare(actual, profile=profile, base=base, expected=expected):
            run.check_prediction(actual, profile.pc, profile.tag_history, base, expected=expected,
                position=6, index_pc=profile.index_pc, index_history=profile.index_history)
        transfers.append(run.agent.submit_predict(profile.pc, 6, base, folded_history=profile.tag_history,
            index_pc=profile.index_pc, index_history=profile.index_history, expected=compare))
    await run.agent.drain_predictions()
    run.check((TransferState.COMPLETED,) * len(transfers), tuple(t.state for t in transfers),
              point='all staged requests completed through bound Scoreboard')
    run.check(True, all(t.accepted_event is not None and t.completed_event is not None for t in transfers),
              point='completed staged transfers retain both real boundary events')
    accepted = tuple(t.accepted_event.tick for t in transfers)
    completed = tuple(t.completed_event.tick for t in transfers)
    run.check(tuple(accepted[0] + 2 * i for i in range(len(transfers))), accepted,
              point='real adjacent lookup acceptance events')
    run.check(tuple(tick + 4 for tick in accepted), completed,
              point='each staged response completes at the declared two-cycle latency')
    return [dict(pc=t.request.pc, index_pc=t.request.read_pc, accepted_tick=a, completed_tick=c)
            for t, a, c in zip(transfers, accepted, completed, strict=True)]
