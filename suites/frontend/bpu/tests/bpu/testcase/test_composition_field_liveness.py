"""Combination-layer dead-field audit (ICache lesson: no compared field may be inert).

The pipeline checker compares a large, source-dependent set of keys.  Fault
injection elsewhere proves the *valid/fire/flush/pc/choice/repair* families are
live; this case proves the **combination-layer sections** are live by tallying,
for every compared key, how many distinct values actually appeared in a real
program.  A key that never varies on either side cannot falsify anything, so the
audit asserts that the critical comparison families do vary and reports the
static remainder explicitly instead of calling it "covered".
"""

from __future__ import annotations

import json
from collections import defaultdict

import pytest

from suites.frontend.bpu.bpu.case.early_direction import discover_negative_path
from suites.frontend.bpu.bpu.checker.early_direction_learning import EarlyDirectionChecks
from suites.frontend.bpu.bpu.checker.pipeline import PipelineChecker
from suites.frontend.bpu.bpu.coverage.early_direction import EarlyDirectionCoverage
from suites.frontend.bpu.bpu.env.early_direction import early_direction_program

PC = 0x40000000


class FieldTally(PipelineChecker):
    """Tally the distinct expected/actual values of every compared key."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.values = defaultdict(set)
        self.actuals = defaultdict(set)
        self.samples = 0

    def capture(self, row, event):
        super().capture(row, event)
        if self.failure is not None or not self.records or self.last_tick != event.tick:
            return
        record = self.records[-1]
        self.samples += 1
        for key, value in _flatten(record['expected']):
            self.values[key].add(value)
        for key, value in _flatten(record['actual']):
            self.actuals[key].add(value)


def _flatten(mapping, prefix=''):
    """Yield dotted leaf (key, value) pairs so each field is tallied alone."""
    for key, value in mapping.items():
        name = f'{prefix}{key}'
        if isinstance(value, dict):
            yield from _flatten(value, name + '.')
        elif isinstance(value, (list, tuple)) and value and isinstance(value[0], dict):
            for index, item in enumerate(value):
                yield from _flatten(item, f'{name}.{index}.')
        elif isinstance(value, set):
            yield name, tuple(sorted(map(str, value)))
        else:
            yield name, value


@pytest.mark.feature("BPU-INT-109")
@pytest.mark.feature("BPU-INT-108")
async def test_combination_layer_compared_fields_are_not_inert(bpu_agent, request):
    coverage = EarlyDirectionCoverage('byte-tag-control')
    checks = EarlyDirectionChecks(coverage, PC)
    async with early_direction_program(bpu_agent, PC, checks,
                                       checker_factory=FieldTally) as env:
        await discover_negative_path(env, checks)
        witness = env.checker
        assert isinstance(witness, FieldTally)
        expected = {key: len(values) for key, values in witness.values.items()}
        actual = {key: len(values) for key, values in witness.actuals.items()}
        evidence = dict(samples=witness.samples,
                        expected_distinct=expected, actual_distinct=actual)

    # Families that must provably vary on both sides: a constant comparison
    # cannot detect a wrong DUT value.
    required = ['prediction.taken', 'prediction.target', 'prediction.position',
                'metadata.history.phrLowBits', 'ahead.meta_valid', 'early_source']
    for key in required:
        assert expected.get(key, 0) >= 2, (key, expected.get(key), evidence)
    for key in ('prediction.taken', 'metadata.history.phrLowBits'):
        assert actual.get(key, 0) >= 2, (key, actual.get(key), evidence)

    # Ahead/Main/TAGE metadata hit maps must move between hit and miss.
    ahead_hit_keys = [key for key in expected if key.startswith('ahead.') and key.endswith('.meta_hit')]
    assert ahead_hit_keys, expected
    assert any(expected[key] >= 2 for key in ahead_hit_keys), ahead_hit_keys

    # A process-global path is reclaimed with the worker sandbox; keep the
    # durable copy on the pytest user properties like the other witnesses.
    request.node.user_properties.append(
        ('combination_field_tally', json.dumps(evidence, sort_keys=True, default=str)))
