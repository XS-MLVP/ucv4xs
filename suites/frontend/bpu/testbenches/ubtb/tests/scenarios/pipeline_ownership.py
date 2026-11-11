"""Different branch identities and misses must not exchange pipeline results."""
from copy import deepcopy
from dataclasses import asdict

from toffee import Scoreboard

from suites.frontend.bpu.testbenches.shared.checker.pipeline_ownership import check_batch_completed
from suites.frontend.bpu.testbenches.shared.checker.pipeline_ownership import check_owned_stream
from suites.frontend.bpu.testbenches.shared.coverage.pipeline_ownership import RULES
from suites.frontend.bpu.testbenches.ubtb.model.vectors import CONDITIONAL
from suites.frontend.bpu.testbenches.ubtb.model.vectors import DIRECT
from suites.frontend.bpu.testbenches.ubtb.model.vectors import INDIRECT
from suites.frontend.bpu.testbenches.ubtb.model.vectors import NOT_TAKEN
from suites.frontend.bpu.testbenches.ubtb.checker.assertions import expected_prediction
from suites.frontend.bpu.testbenches.ubtb.checker.assertions import train_taken
from suites.frontend.bpu.testbenches.ubtb.transactions.types import PredictRequest


async def check_pipeline_ownership(agent, coverage):
    board = Scoreboard('ubtb.distinguishable-requests')
    await agent.reset()
    vectors = (DIRECT, CONDITIONAL, INDIRECT)
    for vector in vectors:
        await train_taken(agent, vector)
    coverage.record('reached', 'distinct-learning')
    sequence = (DIRECT, None, CONDITIONAL, INDIRECT, None, DIRECT, INDIRECT, CONDITIONAL)
    if coverage.profile == 'reverse':
        sequence = tuple(reversed(sequence))
    snapshots = []
    rounds = []
    finished = False
    before_reference = agent.reference.board.status.checked
    try:
        for order in (sequence, tuple(reversed(sequence))):
            requests = tuple(PredictRequest(NOT_TAKEN.pc if vector is None else vector.pc) for vector in order)
            before = agent.prediction_scoreboard.status
            transfers = tuple(agent.submit_predict(request.pc) for request in requests)
            await agent.drain_predictions()
            receipts = check_owned_stream(transfers, requests, strict_overlap=False)
            coverage.record('reached', 'overlapping-originals')
            actuals = tuple([await transfer for transfer in transfers])
            for vector, actual in zip(order, actuals, strict=True):
                board.check(expected=dict(valid=0) if vector is None else asdict(expected_prediction(vector)),
                    actual=dict(valid=0) if not actual.valid else asdict(actual))
            check_batch_completed(before, agent.prediction_scoreboard.status, len(transfers))
            coverage.record('reached', 'owned-hits-and-misses')
            for original, frozen in snapshots:
                board.check(expected=frozen, actual=original)
            snapshots.extend((actual, deepcopy(actual)) for actual in actuals)
            rounds.append(dict(receipts=[dict(row, request=asdict(row['request'])) for row in receipts],
                               hits=[bool(actual.valid) for actual in actuals],
                               targets=[actual.target if actual.valid else None for actual in actuals]))
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
