"""Vary history alone, then vary both PC and history, through the same pipeline."""
from copy import deepcopy
from dataclasses import asdict

from toffee import Scoreboard

from suites.frontend.bpu.checkers.pipeline_ownership import check_batch_completed, check_owned_stream
from suites.frontend.bpu.coverage.pipeline_ownership import RULES
from suites.frontend.bpu.ittage.case.definitions import PC, POSITION
from suites.frontend.bpu.ittage.transaction.types import IttageLookup, IttageTraining


async def check_pipeline_ownership(agent, coverage):
    board = Scoreboard('ittage.distinguishable-contexts')
    await agent.reset()
    vary_pc = coverage.profile.startswith('pc-and-history-')
    owners = tuple((IttageLookup(PC + (0x20 * index if vary_pc else 0), history), target)
        for index, (history, target) in enumerate(((0, 0x40002000), (4, 0x40006000), (8, 0x40009000))))
    miss = (IttageLookup(PC + 0x100, 12), None)
    for request, target in owners:
        cold = await agent.predict(request.pc, folded_history=request.folded_history)
        await agent.train(IttageTraining(request.pc, POSITION, target, cold.meta, 1,
                                        folded_history=request.folded_history))
    coverage.record('reached', 'distinct-learning')
    sequence = (owners[0], miss, owners[1], owners[2], miss, owners[0], owners[2], owners[1])
    if coverage.profile.endswith('-reverse'):
        sequence = tuple(reversed(sequence))
    snapshots = []
    rounds = []
    finished = False
    before_reference = agent.reference.board.status.checked
    try:
        for order in (sequence, tuple(reversed(sequence))):
            requests = tuple(request for request, target in order)
            before = agent.prediction_scoreboard.status
            transfers = tuple(agent.submit_predict(request.pc, folded_history=request.folded_history) for request in requests)
            await agent.drain_predictions()
            receipts = check_owned_stream(transfers, requests, strict_overlap=True)
            coverage.record('reached', 'overlapping-originals')
            actuals = tuple([await transfer for transfer in transfers])
            for (_, target), actual in zip(order, actuals, strict=True):
                board.check(expected=dict(hit=0) if target is None else dict(hit=1, target=target),
                            actual=dict(hit=0) if not actual.hit else dict(hit=actual.hit, target=actual.target))
            check_batch_completed(before, agent.prediction_scoreboard.status, len(transfers))
            coverage.record('reached', 'owned-hits-and-misses')
            for original, frozen in snapshots:
                board.check(expected=frozen, actual=original)
            snapshots.extend((actual, deepcopy(actual)) for actual in actuals)
            rounds.append(dict(receipts=[dict(row, request=asdict(row['request'])) for row in receipts],
                hits=[bool(actual.hit) for actual in actuals],
                targets=[actual.target if actual.hit else None for actual in actuals]))
        agent.reference.raise_failure()
        board.check(expected=True, actual=agent.reference.board.status.checked >= before_reference + sum(len(row['receipts']) for row in rounds))
        board.check(expected=0, actual=agent.reference.board.status.failed)
        coverage.record('reached', 'immutable-original-snapshots')
        coverage.record('reached', 'learning-survives-queries')
        for rule in RULES:
            coverage.record('checked', rule)
        finished = True
    finally:
        coverage.evidence = dict(profile=coverage.profile, rounds=rounds,
            status='PASS' if finished else 'FAIL')
