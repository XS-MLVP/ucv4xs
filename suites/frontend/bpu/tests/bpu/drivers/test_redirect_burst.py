"""Coherent batched recovery accepts complete observed beats, not guesses."""
from copy import deepcopy
from types import SimpleNamespace as NS

import pytest

from suites.frontend.bpu.bpu.env.phr.observation import BpuPhrObservation


class Checks:
    def __init__(self):
        self.last_tick, self.records, self.planned = 10, [], []

    def raise_failure(self):
        pass

    def check(self, expected, actual, **context):
        assert expected == actual, (context, expected, actual)

    def plan(self, payload):
        self.planned.append(deepcopy(payload))


@pytest.mark.asyncio
@pytest.mark.parametrize('fault', (None, 'missing', 'extra', 'reordered', 'payload', 'gap', 'wrong-completion'))
async def test_burst_receipts_require_every_complete_adjacent_payload(fault):
    checks = Checks()
    payloads = ({'source': 7, 'target': 11}, {'source': 3, 'target': 19})
    agent = NS()
    scope = BpuPhrObservation(agent, checks)
    scope._active, agent._phr_observation = True, scope

    async def send_many(items):
        assert tuple(checks.planned) == tuple(items) == payloads
        rows = [dict(tick=12+2*i, public_redirect=dict(valid=1, bits=deepcopy(p))) for i,p in enumerate(items)]
        if fault == 'missing':
            rows.pop()
        elif fault == 'extra':
            rows.append(dict(tick=16, public_redirect=dict(valid=1, bits=items[-1])))
        elif fault == 'reordered':
            rows[0]['public_redirect']['bits'], rows[1]['public_redirect']['bits'] = rows[1]['public_redirect']['bits'], rows[0]['public_redirect']['bits']
        elif fault == 'payload':
            rows[1]['public_redirect']['bits']['source'] = 8
        elif fault == 'gap':
            rows[1]['tick'] += 2
        checks.records.extend(rows)
        return NS(tick=18 if fault == 'wrong-completion' else 16)

    agent.redirect_driver = NS(send_many=send_many)
    if fault:
        with pytest.raises(AssertionError):
            await scope.redirect_many(payloads)
    else:
        assert await scope.redirect_many(payloads) == (12, 14)
        assert [r['observed_tick'] for r in scope.accepted] == [12, 14]


@pytest.mark.asyncio
async def test_empty_burst_cannot_register_or_drive_a_plan():
    checks = Checks()
    agent = NS()
    scope = BpuPhrObservation(agent, checks)
    scope._active, agent._phr_observation = True, scope
    with pytest.raises(ValueError):
        await scope.redirect_many(())
    assert checks.planned == []
