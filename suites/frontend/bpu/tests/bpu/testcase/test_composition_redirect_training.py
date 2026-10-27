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

import asyncio
import json

import pytest

from bpuverify.abtb.model.semantic import coordinate
from bpuverify.bpu.case.early_direction import discover_negative_path
from bpuverify.bpu.checker.early_direction_learning import EarlyDirectionChecks
from bpuverify.bpu.checker.pipeline import PipelineChecker
from bpuverify.bpu.coverage.early_direction import EarlyDirectionCoverage
from bpuverify.bpu.env.early_direction import early_direction_program
from bpuverify.bpu.model.ahead_sources import history_feature
from bpuverify.bpu.transaction.types import BpuBatchTraining, BpuBranchFeedback, BpuRedirect
from bpuverify.common.env.artifacts import write_output
from bpuverify.common.env.paths import REPO_ROOT

PC = 0x40000000


class CollisionChecker(PipelineChecker):
    """Record cycles where a redirect and a training beat were both accepted."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.collisions = []

    def capture(self, row, event):
        super().capture(row, event)
        if self.failure is not None or not self.records or self.last_tick != event.tick:
            return
        expected = self.records[-1]['expected']
        redirect = bool(expected.get('flushes', (0, 0, 0))[2])
        training = row['inputs']['training']
        if not redirect or not (training['valid'] and training['ready']):
            return
        events = self.last_events
        self.collisions.append(dict(
            tick=event.tick,
            model_has_redirect=events.redirect is not None,
            model_has_feedback=events.feedback is not None,
            middle_repair=expected.get('repair2'),
            final_repair=expected.get('repair3'),
        ))


class HistoryIndexChecker(CollisionChecker):
    """Record which path-history feature the model chose for the next ABTB read.

    A redirect advances the live history in the same boundary where a training
    beat is accepted.  The reference chooses the *origin* checkpoint's feature
    for the following AheadBTB read (``old_history`` returns
    ``events.redirect.source``).  This checker records both candidate features
    and the coordinates they would produce, so the choice can be checked and
    shown to be discriminating rather than vacuous.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.awaiting = None
        self.later_reads = []

    def capture(self, row, event):
        super().capture(row, event)
        if self.failure is not None or not self.records or self.last_tick != event.tick:
            return
        expected, actual = self.records[-1]['expected'], self.records[-1]['actual']
        if self.awaiting is not None:
            # A redirect makes the presented frame invalid on its own boundary,
            # so the read issued there is presented several cycles later.  The
            # read is identified by its PC (the redirect target), which no other
            # request in this window uses.  Record every later selecting read so
            # the witness can prove the coordinate could only come from it.
            events = self.last_events
            if events is not None:
                ahead_events = self.model.sources.last_ahead_events
                if ahead_events is not None and ahead_events.select:
                    self.later_reads.append(dict(tick=event.tick, read_pc=ahead_events.read_pc,
                        history=ahead_events.history))
            ahead = expected.get('ahead')
            if isinstance(ahead, dict) and ahead.get('row') is not None:
                self.awaiting.update(
                    next_tick=event.tick,
                    next_row=ahead.get('row'),
                    next_banks=ahead.get('banks'),
                    next_actual_row=actual['ahead'].get('row'),
                    next_actual_banks=actual['ahead'].get('banks'),
                    later_reads=list(self.later_reads),
                )
                self.awaiting = None
            elif event.tick > self.awaiting['tick'] + 32:
                self.awaiting = None
        if not self.collisions:
            return
        record = self.collisions[-1]
        if record['tick'] != event.tick or 'index_used' in record:
            return
        events, cycle = self.last_events, self.last_cycle
        if events is None or events.feedback is None or cycle is None:
            return
        origin = events.feedback.source
        live = self.model.history.history
        origin_feature = history_feature(origin)
        live_feature = live % 16
        read_pc = cycle.next_pc
        origin_coordinate = coordinate(read_pc, origin_feature)
        live_coordinate = coordinate(read_pc, live_feature)
        record.update(
            origin_history=origin.history,
            live_history=live,
            history_advanced=origin.history != live,
            origin_feature=origin_feature,
            live_feature=live_feature,
            index_used=self.model.sources.last_ahead_events.history,
            origin_coordinate=origin_coordinate,
            live_coordinate=live_coordinate,
            coordinates_differ=origin_coordinate != live_coordinate,
            read_pc=read_pc,
        )
        self.awaiting = record


async def drive_collision(agent, checker_factory, choose_target=None):
    """Run the real program, then co-launch one training beat and one redirect."""

    coverage = EarlyDirectionCoverage('byte-tag-control')
    checks = EarlyDirectionChecks(coverage, PC)
    async with early_direction_program(agent, PC, checks,
                                       checker_factory=checker_factory) as env:
        anchor = await discover_negative_path(env, checks)
        witness = env.checker
        assert isinstance(witness, checker_factory)
        assert not witness.collisions, (
            'the program already produced a collision; the co-launch below would be redundant',
            witness.collisions)

        # Two independent pulse drivers, launched in the same cycle.
        transaction = BpuBatchTraining(
            PC, anchor.meta.resolve,
            (BpuBranchFeedback(2, PC, 1, taken=0, mispredict=1),))
        witness.plan_feedback(anchor, transaction)
        target = PC if choose_target is None else choose_target(witness.source_token(anchor))
        request = BpuRedirect(target, anchor.meta.redirect, cfi_pc=PC + 4)
        witness.plan_redirect(anchor, request)
        training = asyncio.create_task(agent.train_batch(transaction))
        await agent.redirect(request)
        await training
        await agent.set_ready(prediction=True, meta=True)
        if hasattr(witness, 'awaiting'):
            # The semantic obligation is on the *next* compared boundary; wait
            # for it instead of assuming the harness already sampled it.
            await env.observation.wait('post_collision_boundary_compared',
                                       lambda _: witness.awaiting is None,
                                       timeout_cycles=32)
        witness.raise_failure()
        return witness


@pytest.mark.feature("BPU-INT-110")
async def test_redirect_and_training_accepted_in_one_cycle_are_both_modelled(bpu_agent):
    witness = await drive_collision(bpu_agent, CollisionChecker)
    cycles = witness.collisions
    # (1) The collision cell really happened.
    assert cycles, ('no cycle accepted a redirect and a training beat '
                    'together', dict(witness.counts))
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


def discriminating_target(token):
    """Pick a redirect target whose history contribution changes the low bits.

    ``PathHistoryReference.advance`` sets the low four bits of the new history to
    ``(target // 2) % 16`` (the ``(pc % 512) * 16`` term contributes zeros).  The
    origin feature is the training origin's ``history % 16``.  Choosing a target
    whose contribution differs makes the two candidate indices distinguishable,
    so the DUT's per-cycle ``ahead.row``/``banks`` comparison can falsify a
    writeback that used the advanced history.
    """

    origin_feature = token.history.history % 16
    for target in (PC + 2 * step for step in range(16)):
        if (target // 2) % 16 != origin_feature:
            return target
    raise AssertionError('no redirect target discriminates the two history features')


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

    witness = await drive_collision(bpu_agent, HistoryIndexChecker,
                                    choose_target=discriminating_target)
    cycles = witness.collisions
    assert cycles, ('no cycle accepted a redirect and a training beat together',
                    dict(witness.counts))
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
