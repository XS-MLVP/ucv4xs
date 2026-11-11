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

import pytest


PC = 0x40000000


@pytest.mark.feature("BPU-INT-109")
@pytest.mark.feature("BPU-INT-108")
async def test_combination_layer_compared_fields_are_not_inert(bpu_agent, request):
    evidence = await bpu_agent.compare_early_composition(pc=PC, probe='field-liveness')
    expected, actual = evidence['expected_distinct'], evidence['actual_distinct']

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
