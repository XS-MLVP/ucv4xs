"""PHR profiles use history windows and XOR folding, not uniform writes."""
from suites.frontend.bpu.models.configuration import *

import pytest

from suites.frontend.bpu.models.folded_history import PHR_FOLD_LAYOUT
from suites.frontend.bpu.models.folded_history import folded_history_values
from suites.frontend.bpu.models.folded_history import validate_folded_history_layout


@pytest.mark.parametrize("history", (0, 8, 15, 32, 256, 512, 2048, 65536, (1 << PHR_BITS) - 1, (1 << PHR_STORAGE_BITS) - 1))
def test_phr_profile_matches_bitwise_window_xor(history):
    # Independent bit-by-bit oracle, not the encoder's chunk algorithm.
    expected = []
    for length, width in PHR_FOLD_LAYOUT:
        folded = 0
        for bit in range(length):
            folded ^= ((history >> bit) & 1) << (bit % width)
        expected.append({"foldedHist": folded})
    assert folded_history_values(history, len(PHR_FOLDS)) == tuple(expected)
    if history < 16:
        assert expected == [{"foldedHist": history}] * len(PHR_FOLDS)


@pytest.mark.parametrize("history", (-1, 1 << PHR_STORAGE_BITS, 1.5))
def test_phr_profile_rejects_invalid_history(history):
    with pytest.raises(ValueError, match=f"{PHR_STORAGE_BITS} bits"):
        folded_history_values(history, len(PHR_FOLDS))


def test_phr_profile_rejects_another_dut_layout():
    with pytest.raises(ValueError, match=f"{len(PHR_FOLDS)} folds"):
        folded_history_values(256, 18)
    widths = [width for _, width in PHR_FOLD_LAYOUT]
    validate_folded_history_layout(widths)
    widths[9] += 1
    with pytest.raises(ValueError, match="layout differs"):
        validate_folded_history_layout(widths)
