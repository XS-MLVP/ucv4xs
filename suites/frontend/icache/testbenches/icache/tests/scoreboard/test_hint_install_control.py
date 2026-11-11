"""Red/green control for the ICACHE-012 hint-installation oracle.

This is a checker self-check, not a hardware functional point.  It keeps the
distinguishing power of ``test_software_prefetch_warms_the_requested_line``
reviewable after that case was promoted to a normal positive test: the oracle
must call a line installed in its own set a hit, and a line installed in the
stale previous-request set a miss.  Without the second half the promoted test
could pass for the wrong reason (the demand model predicting no refill
regardless of where the RTL installed the line).
"""

from __future__ import annotations

import pytest

from suites.frontend.icache.testbenches.icache.model.icache import ICacheIntegrationModel
from suites.frontend.icache.testbenches.icache.model.icache import get_idx


pytestmark = pytest.mark.selftest

VADDR = 0xB000
BLOCK = VADDR >> 6
OWN_SET = get_idx(VADDR)


def test_green_control_hint_in_its_own_set_is_resident():
    model = ICacheIntegrationModel()
    assert model.hit_mask(BLOCK, OWN_SET) == 0
    model.install(BLOCK, OWN_SET)
    assert model.hit_mask(BLOCK, OWN_SET) != 0


def test_red_control_hint_in_the_stale_set_is_not_resident():
    """The old defect installed the line in the *previous* request's set (0).

    On the old baseline the first hint after reset used set 0, so a request in
    any other set was unreachable.  The oracle must report that line as absent
    from the request's own set, which is what makes the promoted test fail if
    the stale-register behaviour ever returns.
    """
    assert OWN_SET != 0
    model = ICacheIntegrationModel()
    model.install(BLOCK, 0)
    assert model.hit_mask(BLOCK, OWN_SET) == 0
