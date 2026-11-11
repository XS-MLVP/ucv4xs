"""Fixture boundary: out-of-domain encodings must be rejected before a pin."""

from __future__ import annotations

import pytest

from suites.frontend.ftq.testbenches.ftq.transactions.types import BackendRedirect
from suites.frontend.ftq.testbenches.ftq.transactions.types import IfuRedirect
from suites.frontend.ftq.testbenches.ftq.transactions.types import Meta
from suites.frontend.ftq.testbenches.ftq.transactions.types import Prediction
from suites.frontend.ftq.testbenches.ftq.env.harness import FtqDutHarness
from suites.frontend.ftq.testbenches.resolve_queue.transactions.types import ResolveReport


def report(**overrides):
    values = dict(index=0, pc=0x8000_0000, offset=1, target=0x8000_3000)
    values.update(overrides)
    return ResolveReport(**values)


@pytest.mark.selftest
@pytest.mark.parametrize("builder,kwargs", [
    (lambda: Prediction(0x8000_0000, end_position=32), {}),
    (lambda: Prediction(1 << 50), {}),
    (lambda: Prediction(0x8000_0000, taken=2), {}),
    (lambda: Meta(64), {}),
    (lambda: Meta(0, flag=2), {}),
    (lambda: BackendRedirect(0, level=2), {}),
    (lambda: BackendRedirect(0, offset=32), {}),
    (lambda: BackendRedirect(0, branch_type=4), {}),
    (lambda: BackendRedirect(0, ipf=1, igpf=1), {}),
    (lambda: IfuRedirect(0, ras_action=4), {}),
    (lambda: report(offset=32), {}),
    (lambda: report(index=64), {}),
    (lambda: report(taken=2), {}),
])
def test_transactions_reject_out_of_domain_values(builder, kwargs):
    with pytest.raises(ValueError):
        builder()


@pytest.mark.selftest
def test_pointer_comparison_matches_circular_semantics():
    older = (0, 63)
    newer = (1, 0)
    assert FtqDutHarness._after(newer, older)
    assert not FtqDutHarness._after(older, newer)
    assert FtqDutHarness._full((0, 0), (1, 0))
    assert not FtqDutHarness._full((0, 0), (1, 1))
    assert FtqDutHarness._distance(newer, older) == 1
    assert FtqDutHarness._distance((0, 0), (1, 0)) == 64
