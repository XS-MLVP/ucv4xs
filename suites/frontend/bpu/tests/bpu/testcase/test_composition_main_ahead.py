"""MainBTB and AheadBTB must be compared together when both hit in one cycle.

``BPU-INT-108`` proved that one redirect is compared against both predictor
windows.  This case covers the other high-risk interaction: the two *branch
target* predictors serving the same pipeline slot at the same time.

The independent model gives each its own stage: AheadBTB feeds the S1 early
choice, MainBTB feeds the S2 choice.  Nothing in the harness previously asserted
that a cycle exists where **both** windows are live and compared; a run could be
fully green while the two never met.

So this is a reach/arbitration witness, not a new golden:
* at least one compared cycle contains both ``ahead`` and ``main_metadata``;
* on at least one of those cycles both windows carry a real hit, so the
  comparison is not two empty windows agreeing;
* on such a cycle the model-derived early source is an AheadBTB source rather
  than fallthrough, and a stage-2 choice exists, i.e. the arbitration produced a
  defined answer instead of silently dropping one side.
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
AHEAD_SOURCES = (1, 3)  # 1 = ahead, 3 = ahead-direction


class BothLiveChecker(PipelineChecker):
    """Record cycles where both branch-target windows were compared."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.both_compared = []

    def capture(self, row, event):
        super().capture(row, event)
        if self.failure is not None or not self.records or self.last_tick != event.tick:
            return
        expected = self.records[-1]['expected']
        if 'ahead' not in expected or 'main_metadata' not in expected:
            return
        ahead = expected['ahead']
        main = expected['main_metadata']
        self.both_compared.append(dict(
            tick=event.tick,
            ahead_hits=tuple(ahead.get(f'{way}.meta_hit') for way in range(4)),
            main_hits=tuple(main[f'{alignment}.{way}.hit']
                            for alignment in range(2) for way in range(2)),
            early_source=expected.get('early_source'),
            choice2=expected.get('choice2'),
        ))


@pytest.mark.feature("BPU-INT-109")
async def test_main_and_ahead_btb_are_compared_together_when_both_hit(bpu_agent):
    coverage = EarlyDirectionCoverage('byte-tag-control')
    checks = EarlyDirectionChecks(coverage, PC)
    async with early_direction_program(bpu_agent, PC, checks,
                                       checker_factory=BothLiveChecker) as env:
        await discover_negative_path(env, checks)
        witness = env.checker
        assert isinstance(witness, BothLiveChecker)

    cycles = witness.both_compared
    # (1) The composition cell must be exercised at all.
    assert cycles, ("no cycle compared both branch-target windows",
                    dict(witness.counts))
    # (2) Not two empty windows: both sides must carry a real hit in ≥1 cycle.
    live = [row for row in cycles
            if any(row['ahead_hits']) and any(row['main_hits'])]
    assert live, ("both windows were compared but never both live", cycles[:6])
    # (3) The arbitration produced a defined early source and a stage-2 choice
    # on at least one live cycle, rather than falling through to base.
    arbitrated = [row for row in live
                  if row['early_source'] in AHEAD_SOURCES and row['choice2'] is not None]
    assert arbitrated, ("both live but no cycle showed an ahead-sourced stage-1 "
                        "choice with a stage-2 choice", live[:6])

    write_output(REPO_ROOT / "results" / "bpu" / "main-ahead-witness.json",
                 json.dumps(dict(pc=hex(PC), compared=len(cycles),
                                 both_live=[row['tick'] for row in live],
                                 arbitrated=[row['tick'] for row in arbitrated]),
                            indent=2, sort_keys=True) + "\n")
