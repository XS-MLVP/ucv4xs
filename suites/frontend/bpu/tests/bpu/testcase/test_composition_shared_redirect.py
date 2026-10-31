"""One redirect must be compared against *both* predictor windows and empty both.

``BPU-ABTB-054`` and ``BPU-UTAGE-026`` prove each predictor flushes its own
window.  Neither proves the composition: that a single ``io.fromFtq.redirect``
reaches ABTB and MicroTAGE in the same cycle, that the independent checker
compares both windows on that cycle, and that both windows are actually empty on
the following cycle.

This case is a witness for exactly that, and nothing more.  It does not invent an
RTL expectation; it counts cycles where the redirect pulse is asserted **and**
both ``ahead`` and ``early_direction`` appear in the compared expectation, then
requires the next lossless cycle to report no live entry in either window.  A
zero count means the composition cell was never checked, however green the run
looks.
"""

from __future__ import annotations

import json

import pytest

from suites.frontend.bpu.bpu.case.early_direction import discover_negative_path
from suites.frontend.bpu.bpu.checker.early_direction_learning import EarlyDirectionChecks
from suites.frontend.bpu.bpu.checker.pipeline import PipelineChecker
from suites.frontend.bpu.bpu.coverage.early_direction import EarlyDirectionCoverage
from suites.frontend.bpu.bpu.env.early_direction import early_direction_program
from suites.frontend.bpu.runtime.artifacts import write_output
from suites.frontend.bpu.runtime.paths import REPO_ROOT

PC = 0x40000000


class WitnessChecker(PipelineChecker):
    """Record redirect cycles where both predictor windows were compared.

    The redirect boundary itself is still compared with the *pre-redirect*
    window content: ``AheadSources.advance`` applies the invalidation to the
    next state, not to the current presentation.  The semantic obligation this
    witness adds is therefore the **next** cycle: after one top-level redirect,
    neither window may still present a live entry.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.shared_redirect_cycles = []
        self.post_redirect_cycles = []
        self._pending = None

    @staticmethod
    def _window(expected):
        ahead = expected['ahead']
        early = expected['early_direction']
        return dict(
            ahead_meta_valid=ahead.get('meta_valid'),
            ahead_hits=tuple(ahead.get(f'{way}.meta_hit') for way in range(4)),
            ahead_valids=tuple(ahead.get(f'{way}.valid') for way in range(4)),
            early_hits=early.get('raw_hits'),
            early_valids=tuple(early.get(f'{way}.valid') for way in range(4)),
        )

    def capture(self, row, event):
        redirect_valid = bool(row.get('inputs', {}).get('redirect', {}).get('valid'))
        super().capture(row, event)
        if (self.failure is not None or self.last_tick != event.tick
                or not self.records or self.records[-1]['tick'] != event.tick):
            return
        expected = self.records[-1]['expected']
        both = 'ahead' in expected and 'early_direction' in expected
        if redirect_valid and both:
            record = dict(tick=event.tick, prediction_valid=expected.get('prediction_valid'),
                          **self._window(expected))
            self.shared_redirect_cycles.append(record)
            # A following redirect replaces the obligation; only the adjacent
            # lossless cycle is a valid post-redirect observation.
            self._pending = record
        elif self._pending is not None and event.tick == self._pending['tick'] + 2:
            if both:
                self.post_redirect_cycles.append(dict(
                    tick=event.tick, after=self._pending['tick'], **self._window(expected)))
            self._pending = None


def _live(window):
    return (window['ahead_meta_valid'] == 1
            or any(hit == 1 for hit in window['ahead_hits'] if hit is not None)
            or any(hit == 1 for hit in window['early_hits'] or ()))


@pytest.mark.feature("BPU-INT-108")
async def test_one_redirect_is_compared_against_both_predictor_windows(bpu_agent):
    coverage = EarlyDirectionCoverage('byte-tag-control')
    checks = EarlyDirectionChecks(coverage, PC)
    async with early_direction_program(bpu_agent, PC, checks,
                                       checker_factory=WitnessChecker) as env:
        await discover_negative_path(env, checks)
        witness = env.checker
        assert isinstance(witness, WitnessChecker)
        cycles = witness.shared_redirect_cycles
        post = witness.post_redirect_cycles
        # The environment must have produced at least one redirect boundary;
        # otherwise the composition cell was never exercised at all.
        assert cycles, ("no redirect cycle compared both predictor windows",
                        dict(witness.counts))
        # At least one of those cycles must have carried a live ABTB entry, so
        # the comparison is not vacuous (an all-miss window would trivially
        # "agree" with an all-miss expectation).
        assert any(row['ahead_meta_valid'] == 1 for row in cycles), cycles
        assert any(any(hit == 1 for hit in row['ahead_hits']) for row in cycles), cycles
        # Composition obligation: the cycle after a redirect must present no
        # live entry in either window.  Require at least one such pair whose
        # pre-redirect cycle was live, so the emptying is not vacuous.
        assert post, ("no post-redirect cycle compared both predictor windows", cycles)
        live_before = [row for row in post
                       if _live(next(pre for pre in cycles if pre['tick'] == row['after']))]
        assert live_before, ("no post-redirect pair had a live pre-redirect window", post)
        for row in post:
            assert row['ahead_meta_valid'] == 0, row
            assert all(value == 0 for value in row['ahead_valids']), row
            assert all(value == 0 for value in row['early_valids']), row
            assert not any(hit == 1 for hit in row['early_hits'] or ()), row

    write_output(REPO_ROOT / "results" / "bpu" / "shared-redirect-witness.json",
                 json.dumps(dict(pc=hex(PC), cycles=cycles, post_redirect=post),
                            indent=2, sort_keys=True) + "\n")
