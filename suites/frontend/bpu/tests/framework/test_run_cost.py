"""The cost preview must name the real long pole and the real invalidating edit.

Synthetic fixtures plus the live tree; nothing here runs the DUT, edits the plan
or changes a verdict.
"""
from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pytest

from tools import run_cost


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_hint_parsing_and_chunking_never_split_a_file(tmp_path, monkeypatch):
    monkeypatch.setattr(run_cost, 'ROOT', tmp_path)
    write(tmp_path / 'tests/a/test_big.py', """
import pytest
@pytest.mark.estimated_runtime(600)
async def test_one(): ...
@pytest.mark.estimated_runtime(300)
async def test_two(): ...
""")
    write(tmp_path / 'tests/a/test_small.py', """
async def test_three(): ...
""")
    rows = run_cost.costs(run_cost.selection_files(['tests/a']))
    assert rows[0]['file'].endswith('test_big.py')
    assert rows[0]['hinted_seconds'] == 900 and rows[0]['test_functions'] == 2
    assert rows[-1]['hinted_seconds'] == 0
    groups = run_cost.chunks(rows, 500)
    # A file is never split, even when it alone exceeds the budget, and the
    # remainder goes to its own chunk instead of being packed past the budget.
    assert [group[1] for group in groups] == [['tests/a/test_big.py'], ['tests/a/test_small.py']]
    assert groups[0][0] == 900 and groups[1][0] == 0


def test_unknown_selection_path_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(run_cost, 'ROOT', tmp_path)
    with pytest.raises(SystemExit):
        run_cost.selection_files(['tests/missing'])


def test_epoch_delta_reports_changed_removed_and_ignores_untracked(tmp_path, monkeypatch):
    monkeypatch.setattr(run_cost, 'ROOT', tmp_path)
    tracked = write(tmp_path / 'x.py', 'value = 1\n')
    gone = write(tmp_path / 'y.py', 'value = 2\n')
    run = tmp_path / 'results/run'
    run.mkdir(parents=True)
    (run / 'source-epoch.json').write_text(json.dumps({
        str(tracked.resolve()): sha256(tracked.read_bytes()).hexdigest(),
        str(gone.resolve()): 'deadbeef',
    }))
    write(tmp_path / 'untracked.py', 'other = 3\n')
    write(tmp_path / 'x.py', 'value = 2\n')
    gone.unlink()  # a removed source file must be reported separately
    delta = run_cost.epoch_delta(run)
    assert delta['changed'] == ['x.py']
    assert delta['removed'] == ['y.py']
    assert delta['added'] == []
    # frozen counts what the run captured; current counts what still exists.
    assert delta['frozen_files'] == 2 and delta['current_files'] == 1


# Every hinted BPU program module, reviewed against the 2026-10-21 measured run.
# Adding a hint (or a new megatest) means updating this inventory deliberately.
REVIEWED_HINTED = {
    'tests/bpu/testcase/test_history_working_set.py',
    'tests/bpu/testcase/test_short_context_ownership.py',
    'tests/bpu/testcase/test_sc_provider_role_matrix.py',
    'tests/bpu/testcase/test_training_alignment.py',
    'tests/bpu/testcase/test_sc_used_nonzero.py',
    'tests/bpu/testcase/test_sc_masked_feedback.py',
    'tests/bpu/testcase/test_sc_admission.py',
    'tests/bpu/testcase/test_short_competition.py',
    'tests/bpu/testcase/test_sc_used_physical.py',
    'tests/bpu/testcase/test_statistical_prefix.py',
    'tests/bpu/testcase/test_ahead_working_set.py',
    'tests/bpu/testcase/test_integrated_state.py',
    'tests/bpu/testcase/test_integrated_abtb_counters.py',
    'tests/bpu/testcase/test_sc_threshold_bounds.py',
    'tests/bpu/testcase/test_direction_recovery.py',
    'tests/bpu/testcase/test_early_aging.py',
}


def test_live_tree_reports_the_heaviest_hinted_file():
    rows = run_cost.costs(run_cost.selection_files(['tests/bpu/testcase']))
    he = [row for row in rows if row['hinted_seconds']]
    assert he and he[0]['hinted_seconds'] >= 900
    assert {row['file'] for row in he} == REVIEWED_HINTED, (
        'a new hinted megatest must be reviewed before it lands')
