"""Profile comparisons belong to the outer asynchronous transfer context."""
from copy import deepcopy
from types import SimpleNamespace

import pytest
from toffee import CheckContext
from toffee import Scoreboard
from toffee import ScoreboardMismatch
from toffee import ScoreboardMode

from bpuverify.tage.transaction.types import TagePrediction
from bpuverify.common.checker.prediction import compare_prediction
from tests.tage.diagnostics.retained_owner_probe import read_profiles
from bpuverify.tage.case.way_migration_scenario import snapshot


class Transfer:
    def __init__(self, prediction, expected):
        self.prediction = prediction
        self.expected = expected
        self.accepted_event = SimpleNamespace(tick=4)
        self.completed_event = SimpleNamespace(tick=8)

    def __await__(self):
        async def result():
            return self.prediction
        return result().__await__()


@pytest.mark.parametrize('actual_counter', (6, 7))
async def test_retained_profile_uses_outer_context_and_frozen_expectation(actual_counter):
    profiles = {0:{6:dict(valid=1, taken=1, provider_counter_valid=1, meta={'providerTakenCtr_value':7})}}
    original = deepcopy(profiles)
    prediction = TagePrediction(1, 1, {'providerTakenCtr_value':actual_counter}, 1)
    transfers = []
    checks = Scoreboard('tage.prediction', compare=compare_prediction)
    def submit(pc, position, base, *, expected):
        assert (pc, position, base) == (0, 6, 1)
        transfer = Transfer(prediction, expected)
        transfers.append(transfer)
        return transfer
    async def drain():
        # A caller mutation after submission must not change the expectation.
        profiles[0][6]['meta']['providerTakenCtr_value'] = 0
        for transfer in transfers:
            checks.check(expected=transfer.expected, actual=transfer.prediction,
                context=CheckContext('tage.prediction', ScoreboardMode.ASYNC, sequence_id=23,
                    request={'pc':0, 'position':6}, accepted_event=transfer.accepted_event,
                    observed_event=transfer.completed_event))
    agent = SimpleNamespace(submit_predict=submit, drain_predictions=drain)
    if actual_counter == 7:
        assert await read_profiles(agent, profiles) == {'0x0:6':original[0][6]}
        assert checks.status.passed == 1
    else:
        with pytest.raises(ScoreboardMismatch) as caught:
            await read_profiles(agent, profiles)
        error = caught.value
        assert error.name == 'tage.prediction' and error.context.mode is ScoreboardMode.ASYNC
        assert error.context.sequence_id == 23 and error.context.request == {'pc':0, 'position':6}
        assert error.context.accepted_event.tick == 4 and error.context.observed_event.tick == 8
        assert any(diff.path == 'meta.providerTakenCtr_value' and diff.expected == 7 and diff.actual == 6
                   for diff in error.differences)
        assert all(term in str(error) for term in ('sequence_id:', 'request:', 'accepted_tick:', 'observed_tick:', 'status:'))
        assert checks.status.failed == 1
