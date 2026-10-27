"""Pure path-plan qualification does not execute or pass BPU-INT-103."""
from dataclasses import replace
import json
from pathlib import Path

import pytest

from bpuverify.bpu.model.short_context_ownership import (
    OLDER_PATHS, OWNERS, declared_paths, program, validate_paths)

pytestmark = pytest.mark.toffee_functional_coverage(False)


def test_real_paths_share_short_history_but_not_distinct_branch_learning():
    paths = program()
    assert len(paths) == 4
    assert len({path.short_history for path in paths}) == 1
    assert len({path.branch_pc for path in paths}) == 2
    assert len({path.short_identity for path in paths}) == 2
    assert all(len(path.predecessors) == 8 for path in paths)
    for branch in OWNERS:
        group = tuple(path for path in paths if path.branch == branch)
        assert tuple(path.older_path for path in group) == OLDER_PATHS
        assert group[0].short_identity == group[1].short_identity
        assert group[0].read_indices[1] != group[1].read_indices[1]
        assert group[0].tags[1] != group[1].tags[1]


def test_full_tags_are_derived_and_not_truncated_to_hide_the_existing_defect():
    paths = program()
    assert [path.read_indices for path in paths] == [(128, 320), (128, 352), (200, 264), (200, 296)]
    assert [path.tags for path in paths] == [(5, 165), (5, 39), (1, 168), (1, 42)]
    # DefaultConfig has full eight-bit long tags, including the high bit.
    # Both branches exercise that bit without truncating the semantic tag.
    assert all(paths[index].tags[1] & 128 for index in (0,2))
    assert all(value < 256 for path in paths for value in path.tags)


def test_semantic_requirement_binds_real_lifetimes_not_pure_path_evidence():
    plan = json.loads(Path('verification_plan.json').read_text())
    point, = [point for point in plan['features'] if point['id'] == 'BPU-INT-103']
    assert point['metadata']['implementation_status'] == 'implemented; real-dut-verdict-required'
    assert point['evidence']['coverage'] == dict(
        reached=['kunminghu_v3.bpu.short-context-ownership.reached','kunminghu_v3.bpu.short-context-direction.reached',
                 'kunminghu_v3.bpu.short-cross-branch-working-set.reached'],
        checked=['kunminghu_v3.bpu.short-context-ownership.checked','kunminghu_v3.bpu.short-context-direction.checked',
                 'kunminghu_v3.bpu.short-cross-branch-working-set.checked'])
    assert 'tests/bpu/testcase/test_short_context_ownership.py' in point['evidence']['checks']
    assert 'tests/bpu/scoreboard/test_short_context_ownership.py' not in point['evidence']['checks']


@pytest.mark.parametrize('fault', ('missing-path', 'reordered', 'one-branch',
    'different-short-history', 'same-longer-context', 'different-short-row'))
def test_invalid_topology_cannot_be_called_shared_short_branch_isolation(fault):
    paths = list(declared_paths())
    if fault == 'missing-path': paths.pop()
    elif fault == 'reordered': paths.reverse()
    elif fault == 'one-branch':
        paths[2:] = [replace(path, branch_pc=paths[0].branch_pc) for path in paths[2:]]
    elif fault == 'different-short-history':
        paths[1] = replace(paths[1], match_context=paths[2].read_context)
    elif fault == 'same-longer-context':
        paths[1] = replace(paths[1], read_context=paths[0].read_context)
    elif fault == 'different-short-row':
        paths[1] = replace(paths[1], predecessors=(*paths[1].predecessors[:-1], paths[1].predecessors[-1] ^ 1))
    with pytest.raises(ValueError): validate_paths(tuple(paths))
