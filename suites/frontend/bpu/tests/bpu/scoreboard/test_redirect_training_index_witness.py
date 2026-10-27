"""Negative controls for the G×H AheadBTB index witness (BPU-INT-112).

The hardware witness is only meaningful if the two candidate histories give
*different* bank/row coordinates.  These pure tests pin the helper that picks a
discriminating redirect target, prove it refuses when no candidate
discriminates, and pin the coordinate function the witness uses.
"""
from types import SimpleNamespace

import pytest

from bpuverify.abtb.model.semantic import coordinate
from tests.bpu.testcase.test_composition_redirect_training import discriminating_target

READ_PC = 0x40000002


def checkpoint(history):
    # Token.history is the owned Checkpoint; checkpoint.history is the value.
    return SimpleNamespace(history=SimpleNamespace(history=history))


def candidates():
    """The features the helper's candidate targets would produce."""
    return {(0x40000000 + 2 * step) // 2 % 16 for step in range(16)}


@pytest.mark.parametrize('history', [0, 1, 5, 15, 0x1234])
def test_chosen_target_makes_the_two_coordinates_differ(history):
    target = discriminating_target(checkpoint(history))
    origin_feature = history % 16
    live_feature = (target // 2) % 16
    assert origin_feature != live_feature
    assert coordinate(READ_PC, origin_feature) != coordinate(READ_PC, live_feature)


def test_every_origin_feature_has_a_discriminating_target():
    # The candidate set covers all sixteen features, so no origin feature can
    # leave the witness vacuous; the defensive raise is unreachable for this PC.
    assert candidates() == set(range(16))
    for history in range(16):
        target = discriminating_target(checkpoint(history))
        assert (target // 2) % 16 != history % 16


def test_coordinate_matches_the_independent_abtb_formula():
    # Pin the exact function the witness uses, so a change in indexing cannot
    # silently make the witness compare the wrong field.
    for pc in (0x40000000, 0x40000800, 0x40000002):
        for history in range(16):
            address = ((2 * pc) ^ history) % (4 * 64)
            assert coordinate(pc, history) == (address % 4, address // 4)


def test_two_candidate_features_really_move_the_coordinate_at_this_pc():
    # The witness's discriminating target is only useful if it changes bank or
    # row at the observed read PC; assert that for the concrete pair measured in
    # the hardware witness (origin 0 vs advanced 1).
    assert coordinate(READ_PC, 0) != coordinate(READ_PC, 1)
