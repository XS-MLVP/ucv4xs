"""Portable lifecycle contracts, not substitutes for actual SC hardware checks."""
import ast
import importlib.util
from pathlib import Path
import pytest
from toffee import CoverageDatabase

HERE = Path(__file__).resolve().parents[1] / 'bpu/testcase'
CASES = (
    ('test_sc_provider_role_matrix', 'test_four_key_provider_role_matrix', 'check_provider_roles', dict(case={}), 2),
    ('test_sc_masked_feedback', 'test_adjacent_distinct_mask_sc_feedback_preserves_pending_lanes',
        'check_masked_feedback', dict(case={}), 1),
    ('test_sc_masked_feedback', 'test_drained_sc_masked_entry_reactivates_without_losing_other_lanes',
        'check_masked_feedback', dict(case={}), 1),
    ('test_sc_common_history_training', 'test_actual_common_history_controls_all_table_updates',
        'check_history_training', dict(bank=0, valid=1), 1),
    ('test_sc_nonzero_common_history', 'test_real_nonzero_history_trains_and_reads_back_all_SC_tables',
        'check_nonzero_history', dict(bank=0, direction='forward'), 1),
)


def test_no_mutable_module_global_coverage_collectors():
    for name, *_ in CASES:
        tree = ast.parse((HERE / (name + '.py')).read_text())
        for node in tree.body:
            if isinstance(node, ast.Assign):
                assert not any(isinstance(target, ast.Name) and target.id in ('GROUP', 'GROUPS')
                    for target in node.targets)


@pytest.mark.parametrize('module_name,function,helper,arguments,count', CASES)
async def test_each_case_gets_fresh_origins_and_strict_merge_still_works(
        monkeypatch, tmp_path, module_name, function, helper, arguments, count):
    spec = importlib.util.spec_from_file_location('candidate_' + module_name, HERE / (module_name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    calls = []

    async def capture(agent, output, intent, groups):
        groups = groups if isinstance(groups, tuple) else (groups,)
        assert len(groups) == count and all(group.samples == 0 for group in groups)
        calls.append([group.report() for group in groups])

    monkeypatch.setattr(module, helper, capture)
    for _ in range(2):
        await getattr(module, function)(bpu_agent=object(), bpu_sc_output=tmp_path, **arguments)
    assert len(calls) == 2
    for first, second in zip(*calls, strict=True):
        assert first['instance'] == second['instance']
        assert first['schema_digest'] == second['schema_digest']
        assert set(first['origins']).isdisjoint(second['origins'])
        database = CoverageDatabase.from_dict(dict(format='xreactor-functional-coverage', version=2, groups=[first]))
        database.merge(CoverageDatabase.from_dict(dict(format='xreactor-functional-coverage', version=2, groups=[second])))
