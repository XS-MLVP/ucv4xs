"""Every bound burst response and native acceptance boundary is required."""
from types import SimpleNamespace

import pytest
from toffee import Scoreboard, ScoreboardMismatch, TransferState

from bpuverify.utage.env.lookup import check_lookup_burst
from bpuverify.utage.model.split_context import contexts, neighbor_context
from bpuverify.utage.transaction.types import UtageLookup


@pytest.mark.parametrize('fault', (None, 'empty', 'pending', 'missing_acceptance', 'missing_response',
                                  'nonadjacent', 'late_response', 'wrong_request_response'))
async def test_lookup_burst_has_exact_request_callbacks_and_completion_events(fault):
    inputs = ((contexts()['positive'], 1, (1, 0, 7, 1)), (neighbor_context(), 0, (1, 0, 3, 0)))
    if fault == 'empty': inputs = ()
    board = Scoreboard('split.burst_contract')
    transfers, callbacks, received = [], [], []
    class Agent:
        def submit_predict(self, pc, position, base, *, folded_history, index_pc, index_history, expected):
            request = UtageLookup(pc, position, base, folded_history=folded_history,
                                  index_pc=index_pc, index_history=index_history)
            tick = 10 + 2 * len(transfers)
            transfer = SimpleNamespace(request=request, state=TransferState.COMPLETED,
                accepted_event=SimpleNamespace(tick=tick), completed_event=SimpleNamespace(tick=tick + 4))
            transfers.append(transfer)
            callbacks.append(expected)
            return transfer
        async def drain_predictions(self):
            for transfer, callback in zip(transfers, callbacks, strict=True):
                actual_pc = transfer.request.pc
                if fault == 'wrong_request_response': actual_pc ^= 64
                callback(SimpleNamespace(pc=actual_pc))
            if fault == 'pending': transfers[-1].state = TransferState.PENDING
            elif fault == 'missing_acceptance': transfers[-1].accepted_event = None
            elif fault == 'missing_response': transfers[-1].completed_event = None
            elif fault == 'nonadjacent': transfers[-1].accepted_event.tick += 2
            elif fault == 'late_response': transfers[-1].completed_event.tick += 2
    def check(expected, actual, **details):
        board.check(expected=expected, actual=actual)
    def check_prediction(actual, pc, history, base, **kwargs):
        check(pc, actual.pc)
        received.append(dict(pc=pc, history=history, base=base, **kwargs))
    run = SimpleNamespace(agent=Agent(), check=check, check_prediction=check_prediction)
    if fault is None:
        receipts = await check_lookup_burst(run, inputs)
        assert [(row['accepted_tick'], row['completed_tick']) for row in receipts] == [(10, 14), (12, 16)]
        assert received == [dict(pc=p.pc, history=p.tag_history, base=b, expected=e,
            position=6, index_pc=p.index_pc, index_history=p.index_history) for p, b, e in inputs]
    else:
        with pytest.raises(ScoreboardMismatch):
            await check_lookup_burst(run, inputs)
        if fault == 'empty': assert not transfers
