"""Scope changes collection, never silently skip tests or shrink schemas."""
import pytest

from suites.frontend.bpu.testbenches.bpu.tests import regression
from suites.frontend.bpu.testbenches.mbtb.tests import regression as mbtb_regression


def test_unknown_profile_is_not_a_smaller_fallback():
    with pytest.raises(ValueError, match='unknown regression profile'):
        regression.counter_coordinates('typo')
    with pytest.raises(ValueError, match='unknown regression profile'):
        mbtb_regression.mbtb_replacement_indices('typo')
