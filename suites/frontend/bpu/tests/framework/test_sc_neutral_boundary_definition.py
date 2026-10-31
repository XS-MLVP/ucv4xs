"""A combined boundary obligation cannot borrow an old cold-state PASS."""
import json
from pathlib import Path

import pytest

from suites.frontend.bpu.pytest_plugins.points import validate_plan
from tests.framework.test_parallel_matrices import EXTRA_MATRICES


@pytest.mark.parametrize('identity', ('BPU-SC-005', 'BPU-SC-014'))
def test_neutral_boundary_binds_independent_model_and_complete_source_consumers(identity):
    plan = json.loads(Path('verification_plan.json').read_text())
    validate_plan(plan)
    point = next(row for row in plan['features'] if row['id'] == identity)
    requirement = point['metadata']['neutral_boundary_qualification']
    assert requirement['old_PASS_is_not_combined_boundary_proof']
    assert not requirement['physical_enumeration']
    assert requirement['required_obligations'] == 40 and requirement['profiles'] == 4
    assert requirement['SC_guard_rows_not_explained_by_this_requirement'] == 336
    for status in ('reached', 'checked'):
        assert 'kunminghu_v3.sc.neutral-boundary.' + status in point['evidence']['coverage'][status]
    assert 'sc/model/neutral_boundary.py' in point['evidence']['model']
    assert 'tests/sc/testcase/test_neutral_boundary.py' in point['evidence']['checks']


def test_old_cold_cancellation_keeps_its_own_four_bins_without_fabricated_reached():
    plan = json.loads(Path('verification_plan.json').read_text())
    point = next(row for row in plan['features'] if row['id'] == 'BPU-SC-014')
    factory, axes, cross, denominator = EXTRA_MATRICES['sc_legacy_same_way']
    assert point['metadata']['neutral_boundary_qualification']['legacy_unpaired_checked_groups'] == [factory().instance]
    assert denominator == len(axes['phase']) == 4 and cross is None
    assert factory().instance not in point['evidence']['coverage']['reached']
    assert 'tests/sc/testcase/test_same_way_feedback.py' in point['evidence']['checks']
