"""Commit inputs have exact value domains, not native integer coercions."""
from types import SimpleNamespace

import pytest

from suites.frontend.ftq.commit_queue.agent.main import CommitQueueAgent
from suites.frontend.ftq.commit_queue.checker.model import CommitChecker
from suites.frontend.ftq.oracle import CallRet
from suites.frontend.ftq.ftq.driver.encoding import encode_callret

pytestmark = pytest.mark.selftest


@pytest.mark.parametrize('field,bad', (
    ('ptr', -1), ('ptr', 64), ('ptr', True), ('ptr', 1.0), ('ptr', '1'),
    ('ras', -1), ('ras', 4), ('ras', False), ('ras', 1.0), ('ras', '2'),
))
def test_callret_rejects_lossy_or_out_of_domain_input_before_encoding(field, bad):
    values = dict(ptr=1, ras=2)
    values[field] = bad
    with pytest.raises(ValueError):
        CallRet(**values)


def test_all_pointer_and_action_boundaries_remain_legal():
    for ptr in range(64):
        for ras in range(4):
            value = CallRet(ptr, ras)
            assert value.ptr == ptr and value.ras == ras


@pytest.mark.parametrize('bad', (SimpleNamespace(ptr=1, ras=2), dict(ptr=1, ras=2), 0))
def test_commit_encoder_does_not_accept_unvalidated_duck_typed_payload(bad):
    agent = object.__new__(CommitQueueAgent)
    agent.ports = SimpleNamespace(backend=(None,) * 8)
    rows = (bad,) + (None,) * 7
    with pytest.raises(ValueError, match='CallRet'):
        agent._encode(rows)
    with pytest.raises(ValueError, match='CallRet'):
        encode_callret(bad)


@pytest.mark.parametrize('bad', (SimpleNamespace(ptr=1, ras=2), dict(ptr=1, ras=2), 0))
async def test_rejected_commit_does_not_advance_the_oracle_or_start_a_driver(bad):
    agent = object.__new__(CommitQueueAgent)
    agent.ports = SimpleNamespace(backend=(None,) * 8)
    agent.checker = CommitChecker()
    before = agent.checker.model.enq, agent.checker.model.deq, tuple(agent.checker.model.mem)
    driven = []

    async def unexpected_drive(rows):
        driven.append(rows)
        raise AssertionError('invalid commit reached a driver')

    agent.drive = unexpected_drive
    with pytest.raises(ValueError, match='CallRet'):
        await agent.submit((bad,) + (None,) * 7)
    assert not driven
    assert (agent.checker.model.enq, agent.checker.model.deq, tuple(agent.checker.model.mem)) == before
