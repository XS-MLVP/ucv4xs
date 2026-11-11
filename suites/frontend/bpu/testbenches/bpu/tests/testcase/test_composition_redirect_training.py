"""A redirect and a training beat accepted in the same cycle must both be modelled.

Every existing program drives them apart: sampling 254 compared cycles of the
``early_direction`` program gives 5 redirect cycles and **zero** cycles where the
training port was ready, so the collision cell was never exercised.

This case co-launches the two pulse drivers (they are separate drivers, so the
framework permits it) and then asserts:

1. at least one compared cycle had ``redirect.valid`` **and** ``training.valid &
   ready`` -- the cell really happened;
2. on that cycle the independent model built **both** a ``Redirect`` and a
   ``Feedback`` -- neither event was silently dropped by the harness;
3. the flush that cycle reports is a redirect flush, not a training-induced one.

It is a composition witness: it does not claim that the learned state is correct
after the collision (the per-field comparisons of ``BPU-INT-*`` and the
sub-module cases carry that), only that the collision is genuinely modelled
rather than skipped.
"""

from __future__ import annotations

import json

import pytest

from suites.frontend.bpu.testbenches.abtb.model.semantic import coordinate
# Keep the historical helper import used by the independent index selftests.
from suites.frontend.bpu.testbenches.bpu.checker.composition import discriminating_target
from suites.frontend.bpu.testbenches.shared.env.artifacts import write_output
from suites.frontend.bpu.testbenches.shared.env.paths import REPO_ROOT

PC = 0x40000000


@pytest.mark.feature("BPU-INT-110")
async def test_redirect_and_training_accepted_in_one_cycle_are_both_modelled(bpu_agent):
    witness = await bpu_agent.compare_redirect_training(pc=PC)
    cycles = witness['collisions']
    # (1) The collision cell really happened.
    assert cycles, ('no cycle accepted a redirect and a training beat '
                    'together', witness['counts'])
    # (2) Neither event was dropped: the model built both.
    assert all(row['model_has_redirect'] for row in cycles), cycles
    assert all(row['model_has_feedback'] for row in cycles), cycles
    # (3) The flush on that cycle belongs to the redirect, not to the
    #     training.  Without this assertion the docstring's third claim was
    #     only recorded, never checked.
    assert all(row['middle_repair'] == 0 and row['final_repair'] == 0
               for row in cycles), cycles

    write_output(REPO_ROOT / "results" / "bpu" / "redirect-training-collision.json",
                 json.dumps(dict(pc=hex(PC), collisions=cycles), indent=2, sort_keys=True) + "\n")


@pytest.mark.feature("BPU-INT-112")
async def test_next_aheadbtb_index_uses_the_redirect_origin_history(bpu_agent):
    """G×H: the index must come from the pre-redirect history.

    The same boundary accepts a training beat (a predictor writeback) and
    advances the path history through the redirect.  The following AheadBTB read
    must be indexed by the **redirect origin's** four-bit history feature, not by
    the advanced value.  At least one collision must give the two candidates
    *different* bank/row coordinates, otherwise the cell is vacuous: the DUT's
    per-cycle ``ahead.row``/``banks`` comparison would accept either history.
    """

    witness = await bpu_agent.compare_redirect_training(pc=PC, distinguish_origin=True)
    cycles = witness['collisions']
    assert cycles, ('no cycle accepted a redirect and a training beat together',
                    witness['counts'])
    coincident = [row for row in cycles if row['history_advanced']]
    assert coincident, ('the training boundary did not advance the live history; '
                        'the same-cycle cell was never exercised', cycles)
    discriminating = [row for row in coincident if row['coordinates_differ']]
    assert discriminating, ('the origin and advanced histories give the same '
                            'AheadBTB coordinate, so the cell cannot discriminate', cycles)
    for row in coincident:
        assert row['index_used'] == row['origin_feature'], row
    for row in discriminating:
        assert row['index_used'] != row['live_feature'], row
    # The DUT side: the presented frame must be the collision-cycle read's own
    # result.  Because no later selecting read can produce the origin
    # coordinate, the observed row/bank can only come from that read.
    for row in discriminating:
        bank, at_row = row['origin_coordinate']
        assert row.get('next_row') == at_row, row
        assert row.get('next_banks') == 1 << bank, row
        assert row.get('next_actual_row') == at_row, row
        assert row.get('next_actual_banks') == 1 << bank, row
        later = [item for item in row.get('later_reads') or ()
                 if coordinate(item['read_pc'], item['history'])
                 == (bank, at_row)]
        assert not later, ('a later read also lands on the origin coordinate, '
                           'so this witness cannot attribute the value', row)

    write_output(REPO_ROOT / "results" / "bpu" / "phr-writeback-coincidence.json",
                 json.dumps(dict(pc=hex(PC), collisions=cycles), indent=2, sort_keys=True) + "\n")
