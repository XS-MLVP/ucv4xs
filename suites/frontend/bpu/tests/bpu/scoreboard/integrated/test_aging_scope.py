"""Long aging preserves every original check and uses a finite larger budget."""
import ast
from pathlib import Path
import pytest
from bpuverify.bpu.case.bypass.aging_plan import direction_epochs
from bpuverify.bpu.checker.abtb import checks_general
from bpuverify.bpu.checker.abtb import checks_aging


@pytest.mark.parametrize('count', (1,2,80))
def test_alternating_normal_feedback_epochs(count):
    epochs = direction_epochs(count)
    assert len(epochs) == count
    assert all(tuple(goal for _,goal in pair) == (1,2) for pair in epochs)


@pytest.mark.parametrize('count', (0,-1,True))
def test_nonpositive_and_boolean_bounds_rejected(count):
    with pytest.raises(ValueError):
        direction_epochs(count)


def test_only_the_capacity_changes_in_long_aging_reference():
    old = Path(checks_general.__file__).read_text()
    current = Path(checks_aging.__file__).read_text()
    expected = old.replace('len(self.control_records) < 8192', 'len(self.control_records) < 65536')
    assert ast.dump(ast.parse(current)) == ast.dump(ast.parse(expected))


def test_finite_budget_covers_eighty_original_epoch_windows():
    assert 8192 < 80*518+8192 < 65536
