"""Comparison reachability, not RTL mutations or new hardware features."""
import pytest

from suites.frontend.ftq.testbenches.ftq.tests.checkers.frontend_vectors import composition, corrupt, mutations

pytestmark = pytest.mark.selftest


@pytest.mark.parametrize('redirect', (False, True))
def test_fixed_legal_comparison_vectors(redirect):
    model, frame, data = composition(redirect=redirect)
    model.check_phase(frame, data, 1)


@pytest.mark.parametrize('channel,path,redirect', mutations())
def test_every_meaningful_field_is_actually_compared(channel, path, redirect):
    model, frame, data = composition(redirect=redirect)
    model.check_phase(frame, data, 1)
    data['ftq.' + channel] = corrupt(data['ftq.' + channel], path)
    with pytest.raises(AssertionError):
        model.check_phase(frame, data, 1)
