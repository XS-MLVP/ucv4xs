"""InstrUncacheEntry checker discrimination controls."""

from __future__ import annotations

import pytest
from toffee.scoreboard import ScoreboardMismatch

from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.checker import check_outputs as check_entry_outputs
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import Outputs as EntryOutputs


def _entry(addr=0x3A00_0000, data=0):
    return EntryOutputs(0, 0, data, 0, 0, 0, 1, addr, 0, 0, 1)


@pytest.mark.feature("INC-ENV-002")
def test_entry_checker_rejects_acquire_address_bit():
    expected = _entry(addr=0x3A00_0000)
    actual = _entry(addr=0x3A00_0008)
    with pytest.raises(ScoreboardMismatch):
        check_entry_outputs(expected, actual, phase="discrimination")


@pytest.mark.feature("INC-ENV-002")
def test_entry_checker_rejects_response_data_bit():
    expected = EntryOutputs(0, 1, 0x1234_5678, 0, 0, 0, 0, 0, 0, 0, 1)
    actual = EntryOutputs(0, 1, 0x1234_5679, 0, 0, 0, 0, 0, 0, 0, 1)
    with pytest.raises(ScoreboardMismatch):
        check_entry_outputs(expected, actual, phase="discrimination")
