"""The plan and the executed tests must stay mutually traceable."""

from __future__ import annotations

import pytest

from tools.traceability import audit


@pytest.mark.selftest
def test_every_plan_point_has_a_test_and_every_test_names_a_point():
    assert audit() == []
