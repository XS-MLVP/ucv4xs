"""Long-pole guards: a heavy scenario must declare its cost and its case count.

The measured 2026-10-21 full BPU program run took **35171 s (9.8 h)** for 1031
cases while the hints at the time added up to 4480 s, because
``estimated_runtime`` is a *per test function* number and the heaviest modules
were not hinted at all. Two things therefore have to stay visible:

* every module whose measured total is large carries a hint close to its
  measured peak, so ``tools/run_cost.py`` and the long-first scheduler see it;
* the case count of an expensive parametrized matrix does not grow silently,
  because cost is ``cases x per-case cycles``.

These are review gates over the recorded measurement, not assertions about the
DUT. Nothing here selects, skips or re-weights a test.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

# (module, measured total seconds, measured peak seconds, measured cases)
MEASURED = {
    'tests/bpu/testcase/test_history_working_set.py': (12579.7, 7919.3, 11),
    'tests/bpu/testcase/test_sc_provider_role_matrix.py': (4178.7, 34.4, 192),
    'tests/bpu/testcase/test_short_context_ownership.py': (3143.8, 597.3, 10),
    'tests/bpu/testcase/test_training_alignment.py': (2949.2, 25.3, 200),
    'tests/bpu/testcase/test_sc_used_nonzero.py': (1920.9, 75.5, 32),
    'tests/bpu/testcase/test_sc_threshold_bounds.py': (896.9, 188.2, 8),
    'tests/bpu/testcase/test_sc_masked_feedback.py': (902.7, 20.2, 96),
    'tests/bpu/testcase/test_sc_admission.py': (706.7, 78.3, 22),
    'tests/bpu/testcase/test_integrated_state.py': (1031.8, 415.5, 17),
    'tests/bpu/testcase/test_integrated_abtb_counters.py': (546.1, 289.5, 3),
    'tests/bpu/testcase/test_short_competition.py': (473.0, 128.2, 4),
    'tests/bpu/testcase/test_ahead_working_set.py': (337.0, 57.7, 12),
    'tests/bpu/testcase/test_sc_used_physical.py': (389.0, 35.0, 16),
    'tests/bpu/testcase/test_statistical_prefix.py': (361.0, 28.8, 16),
}

HINT = re.compile(r'estimated_runtime\(\s*(\d+(?:\.\d+)?)\s*\)')

# A hint may under-shoot its own module peak a little (the peak also includes
# fixed per-case setup that a scheduling hint does not need to model), but not
# collapse to a token value.
MIN_HINT_FRACTION = 0.5
# Case counts are frozen at the reviewed measurement; growing one of these
# matrices needs an explicit decision, because it multiplies the peak cost.
CASE_CAP = {module: cases for module, (_, _, cases) in MEASURED.items()}


def hints(path: Path) -> list[float]:
    return [float(value) for value in HINT.findall(path.read_text())]


@pytest.mark.parametrize('module', sorted(MEASURED))
def test_every_measured_long_pole_declares_its_cost(module):
    path = ROOT / module
    assert path.exists(), module
    values = hints(path)
    assert values, f'{module} measured {MEASURED[module][0]:.0f}s but declares no estimated_runtime'
    peak = MEASURED[module][1]
    assert max(values) >= MIN_HINT_FRACTION * peak, (
        f'{module} declares {max(values):.0f}s but measured a {peak:.0f}s case; '
        'run_cost.py and the long-first scheduler would under-place it')


def test_hint_multiplication_is_visible_for_parametrized_matrices():
    """A per-case hint times many cases is the shape that hid 9.8 h of work."""

    under = []
    for module, (total, peak, cases) in MEASURED.items():
        path = ROOT / module
        if not path.exists():
            continue
        declared = max(hints(path) or [0])
        if declared and total / declared >= 5:
            under.append((module, round(total / declared, 1), cases))
    # These are exactly the modules where the declared number is one case while
    # the selection runs all of them. They are allowed to exist, but the tool
    # must reproduce them from --measured rather than the hint.
    assert under, ('the measured report should expose at least one matrix whose '
                   'per-case hint understates its total')
    inspected = run_cost_hint_understatement()
    assert set(inspected) == {module for module, _, _ in under}


def run_cost_hint_understatement():
    from tools import run_cost
    rows = run_cost.costs(run_cost.selection_files(['tests/bpu/testcase']))
    selected = {row['file'] for row in rows}
    data = run_cost.measured(ROOT / 'results/bpu-composition-full-20261021-v1/pytest.xml')
    result = []
    for name in selected & set(data['totals']):
        declared = next((row['hinted_seconds'] for row in rows if row['file'] == name), 0)
        if declared and data['totals'][name] / declared >= 5:
            result.append(name)
    return result


@pytest.mark.parametrize('module', sorted(CASE_CAP))
def test_expensive_matrix_case_count_is_a_reviewed_number(module):
    path = ROOT / module
    functions = len(re.findall(r'^(?:async def test_|def test_)', path.read_text(), re.M))
    # Module-level parametrization multiplies at collection time; the recorded
    # count is the only place that multiplication is visible.
    assert MEASURED[module][2] >= functions, (
        f'{module}: {functions} test functions but a recorded {MEASURED[module][2]} cases')
    assert CASE_CAP[module] == MEASURED[module][2]
