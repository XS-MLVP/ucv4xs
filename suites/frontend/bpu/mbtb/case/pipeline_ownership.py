"""Distinct fetch windows retain their full results across intervening misses."""
from copy import deepcopy
from dataclasses import asdict

from toffee import Scoreboard

from suites.frontend.bpu.checkers.pipeline_ownership import check_batch_completed, check_owned_stream
from suites.frontend.bpu.coverage.pipeline_ownership import RULES
from suites.frontend.bpu.mbtb.case.definitions import BranchVector, DIRECT, MISS_PC
from suites.frontend.bpu.mbtb.checker.assertions import assert_miss, assert_vector_hit, train
from suites.frontend.bpu.mbtb.transaction.types import MbtbLookup


async def check_pipeline_ownership(agent, coverage):
    board = Scoreboard('mbtb.distinguishable-windows')
    await agent.reset()
    direct = DIRECT
    indirect = BranchVector(DIRECT.pc + 0x80, 0x40005560, 9, 3)
    conditional = BranchVector(DIRECT.pc + 0x100, 0x40007780, 1, 1)
    for vector in (direct, indirect, conditional):
        cold = await agent.predict(vector.pc)
        await train(agent, vector, cold.meta_entries)
    coverage.record('reached', 'distinct-learning')
    sequence = (direct, None, conditional, indirect, None, direct, indirect, conditional)
    if coverage.profile == 'reverse':
        sequence = tuple(reversed(sequence))
    snapshots = []
    rounds = []
    finished = False
    before_reference = agent.reference.board.status.checked
    try:
        for order in (sequence, tuple(reversed(sequence))):
            requests = tuple(MbtbLookup(MISS_PC if vector is None else vector.pc) for vector in order)
            before = agent.prediction_scoreboard.status
            transfers = tuple(agent.submit_predict(request.pc) for request in requests)
            await agent.drain_predictions()
            receipts = check_owned_stream(transfers, requests, strict_overlap=True)
            coverage.record('reached', 'overlapping-originals')
            actuals = tuple([await transfer for transfer in transfers])
            for vector, actual in zip(order, actuals, strict=True):
                if vector is None:
                    assert_miss(actual)
                else:
                    assert_vector_hit(actual, vector)
            check_batch_completed(before, agent.prediction_scoreboard.status, len(transfers))
            coverage.record('reached', 'owned-hits-and-misses')
            for original, frozen in snapshots:
                board.check(expected=frozen, actual=original)
            snapshots.extend((actual, deepcopy(actual)) for actual in actuals)
            rounds.append(dict(receipts=[dict(row, request=asdict(row['request'])) for row in receipts],
                entries=[[asdict(entry) for entry in actual.entries if entry.valid] for actual in actuals]))
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
