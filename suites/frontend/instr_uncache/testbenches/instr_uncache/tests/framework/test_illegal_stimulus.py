"""Legal-stimulus guards: protocol-illegal input never reaches the DUT."""

from __future__ import annotations

import pytest

from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import EntryInputs
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import StimulusError
from suites.frontend.instr_uncache.testbenches.instr_uncache.model import Inputs as TopInputs


@pytest.mark.feature("INC-ENV-003")
def test_denied_without_corrupt_is_rejected():
    with pytest.raises(StimulusError, match="denied => corrupt"):
        EntryInputs(grant_valid=1, grant_denied=1, grant_corrupt=0)
    with pytest.raises(StimulusError, match="denied => corrupt"):
        TopInputs(d_valid=1, d_denied=1, d_corrupt=0)


@pytest.mark.feature("INC-ENV-003")
def test_odd_request_address_is_rejected():
    with pytest.raises(StimulusError, match="2-byte aligned"):
        EntryInputs(req_addr=0x3A00_0001)
    with pytest.raises(StimulusError, match="2-byte aligned"):
        TopInputs(req_addr=0x3A00_0001)


@pytest.mark.feature("INC-ENV-003")
def test_legal_denied_stimulus_is_accepted():
    entry = EntryInputs(grant_valid=1, grant_denied=1, grant_corrupt=1)
    top = TopInputs(d_valid=1, d_denied=1, d_corrupt=1)
    assert entry.grant_denied == 1
    assert top.d_denied == 1
