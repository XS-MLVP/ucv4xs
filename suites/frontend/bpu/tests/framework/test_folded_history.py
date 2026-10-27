"""PHR profiles use history windows and XOR folding, not uniform writes."""

import pytest

from bpuverify.common.model.folded_history import PHR_FOLD_LAYOUT
from bpuverify.common.model.folded_history import folded_history_values
from bpuverify.common.model.folded_history import validate_folded_history_layout


@pytest.mark.parametrize("history", (0, 8, 15, 32, 256, 512, 2048, 65536, (1 << 31) - 1))
def test_phr_profile_matches_bitwise_window_xor(history):
    # Independent bit-by-bit oracle, not the encoder's chunk algorithm.
    expected = []
    for length, width in PHR_FOLD_LAYOUT:
        folded = 0
        for bit in range(length):
            folded ^= ((history >> bit) & 1) << (bit % width)
        expected.append({"foldedHist": folded})
    assert folded_history_values(history, 19) == tuple(expected)
    if history < 16:
        assert expected == [{"foldedHist": history}] * 19


@pytest.mark.parametrize("history", (-1, 1 << 31, 1.5))
def test_phr_profile_rejects_invalid_history(history):
    with pytest.raises(ValueError, match="31 bits"):
        folded_history_values(history, 19)


def test_phr_profile_rejects_another_dut_layout():
    with pytest.raises(ValueError, match="19 folds"):
        folded_history_values(256, 18)
    widths = [width for _, width in PHR_FOLD_LAYOUT]
    validate_folded_history_layout(widths)
    widths[9] = 8
    with pytest.raises(ValueError, match="layout differs"):
        validate_folded_history_layout(widths)
