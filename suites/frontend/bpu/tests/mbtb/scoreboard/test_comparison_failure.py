"""Custom consumers cannot hide or duplicate the first semantic failure."""
from types import SimpleNamespace

import pytest

from suites.frontend.bpu.mbtb.agent.main import MbtbAgent
from suites.frontend.bpu.mbtb.checker.semantic import MbtbSemanticChecker


def test_independent_failure_precedes_custom_comparison_and_is_not_raised_twice():
    reference = MbtbSemanticChecker()
    first = AssertionError('first independent discrepancy')
    reference.failure = first
    calls = []
    agent = SimpleNamespace(reference=reference)
    with pytest.raises(AssertionError) as caught:
        MbtbAgent._compare_prediction(agent, lambda actual: calls.append(actual), 'actual')
    assert caught.value is first
    assert reference.failure_observed and calls == []
    reference.raise_unobserved_failure()
    with pytest.raises(AssertionError) as repeated:
        reference.raise_failure()
    assert repeated.value is first  # Failure was observed, not cleared/resynced.


def test_custom_comparison_still_reports_its_own_failure_when_no_model_error_exists():
    agent = SimpleNamespace(reference=MbtbSemanticChecker())
    second = AssertionError('custom consumer discrepancy')

    def custom(actual):
        assert actual == 'actual'
        raise second

    with pytest.raises(AssertionError) as caught:
        MbtbAgent._compare_prediction(agent, custom, 'actual')
    assert caught.value is second
    assert not agent.reference.failure_observed


def test_concrete_and_callable_expectations_both_keep_normal_comparison():
    agent = SimpleNamespace(reference=MbtbSemanticChecker())
    MbtbAgent._compare_prediction(agent, dict(valid=1), dict(valid=1))
    MbtbAgent._compare_prediction(agent, lambda actual: actual['valid'] == 1, dict(valid=1))
    with pytest.raises(AssertionError):
        MbtbAgent._compare_prediction(agent, dict(valid=1), dict(valid=0))
