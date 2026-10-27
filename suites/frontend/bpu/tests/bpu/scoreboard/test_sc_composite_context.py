"""Deadline diagnostics and latched failures stay in reusable check components."""
from types import SimpleNamespace
import pytest
from bpuverify.bpu.checker.sc.history_training import Checks as HistoryChecks
from bpuverify.bpu.checker.sc.nonzero_scenarios import Checks as NonzeroChecks


@pytest.mark.parametrize('checker_type', (HistoryChecks, NonzeroChecks))
def test_composite_forwards_bounded_failure_context(checker_type):
    first = SimpleNamespace(case={'bank': 1}, phase='drive_0', records=[], planned=[], accepts=[], raise_failure=lambda: None)
    checker = checker_type(first)
    for field in ('case', 'phase', 'records', 'planned', 'accepts'):
        assert getattr(checker, field) is getattr(first, field)
    checker.raise_failure()


@pytest.mark.parametrize('checker_type', (HistoryChecks, NonzeroChecks))
def test_composite_propagates_latched_observer_failure(checker_type):
    failure = RuntimeError('latched observer failure')
    def fail():
        raise failure
    checker = checker_type(SimpleNamespace(raise_failure=lambda: None), SimpleNamespace(raise_failure=fail))
    with pytest.raises(RuntimeError, match='latched observer failure') as caught:
        checker.raise_failure()
    assert caught.value is failure
