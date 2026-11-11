"""Semantic scope, normal layering, independent models and complete schemas."""
import ast
import json
from pathlib import Path
import pytest

from suites.frontend.bpu.testbenches.bpu.model.indirect_path_ownership import PROFILES as PATH_PROFILES
from suites.frontend.bpu.testbenches.bpu.model.indirect_path_ownership import RULES as PATH_RULES
from suites.frontend.bpu.testbenches.bpu.model.conditional_prefix import PROFILES as PREFIX_PROFILES
from suites.frontend.bpu.testbenches.bpu.model.conditional_prefix import RULES as PREFIX_RULES
from suites.frontend.bpu.testbenches.bpu.coverage.indirect_path_ownership import lifetime_coverage as path_coverage
from suites.frontend.bpu.testbenches.bpu.coverage.conditional_prefix import lifetime_coverage as prefix_coverage


def test_contracts_define_human_events_before_hardware_credit_not_new_physical_functions():
    for family in ('indirect-path-ownership', 'conditional-prefix'):
        value = json.loads(Path('docs/spec/verification/contracts/bpu-' + family + '-contract.json').read_text())
        assert value['new_feature_IDs'] == 0 and value['independent_components'] == 6
        assert value['no_new_prediction_algorithm'] and value['no_bank_set_way_sweep']
        assert value['no_RTL_DUT_SDK_changes'] and value['ordinary_failures_not_waived']
        assert value['old_joint_profile_excludes_Ahead_scope_retained']
        assert value['existing_features'] == ['BPU-INT-032', 'BPU-INT-034', 'BPU-INT-044', 'BPU-INT-048']
        assert value['title'] and value['prototype_requirement']
        for location in value['source_chain']:
            name, line = location.rsplit(':', 1)
            assert 0 < int(line) <= len(Path(name).read_text().splitlines())


@pytest.mark.parametrize('factory,count', ((path_coverage, 48), (prefix_coverage, 96)))
def test_all_source_obligations_start_empty_and_keep_every_unqualified_profile(factory, count):
    for state in ('reached', 'checked'):
        group = factory(state)
        values = group.report()['points'][0]['counts']
        assert len(values) == count and set(values.values()) == {0}
        assert group.instance.startswith('kunminghu_v3.bpu.') and group.instance.endswith('.' + state)
    assert len(PATH_PROFILES) == 4 and len(PREFIX_PROFILES) == 8
    assert len(PATH_RULES) == len(PREFIX_RULES) == 12


def test_production_modules_import_no_prototypes_or_test_helpers():
    paths = ['model/early_joint_sources.py', 'env/bundle/indirect_guard.py', 'env/monitor/unexecuted_indirect.py']
    paths += [role + '/' + family + '.py' for role in ('model', 'checker', 'coverage', 'tests/scenarios/lifetimes', 'tests/scenarios')
        for family in ('indirect_path_ownership', 'conditional_prefix')]
    for relative in paths:
        path = Path('testbenches/bpu') / relative
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.module is None or not node.module.startswith(('results', 'tests', 'probe', 'native', 'feasibility', 'qualified_'))
            if isinstance(node, ast.Import):
                assert all(not item.name.startswith(('results', 'tests')) for item in node.names)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert not (isinstance(node.func.value, ast.Attribute) and node.func.value.attr == 'path' and node.func.attr == 'insert')


def test_static_bundle_dynamic_monitor_and_semantic_case_remain_separate():
    bundle = ast.parse(Path('testbenches/bpu/env/bundle/indirect_guard.py').read_text())
    assert not any(isinstance(node, (ast.Await, ast.AsyncFunctionDef)) for node in ast.walk(bundle))
    for family in ('indirect_path_ownership', 'conditional_prefix'):
        testcase = ast.parse(Path('testbenches/bpu/tests/testcase/test_' + family + '.py').read_text())
        text = Path('testbenches/bpu/tests/scenarios/' + family + '.py').read_text()
        assert not any(token in text for token in ('FallingEdge', 'RisingEdge', 'ClockCycles', 'get_(', 'set_(', 'asyncio.gather'))
        assert not any(isinstance(node, ast.Name) and node.id in ('FallingEdge', 'RisingEdge', 'ClockCycles') for node in ast.walk(testcase))
        env = ast.parse(Path('testbenches/bpu/tests/scenarios/lifetimes/' + family + '.py').read_text())
        assert not any(isinstance(node, ast.AsyncFunctionDef) and node.name == 'complete' for node in ast.walk(env))
    monitor = Path('testbenches/bpu/env/monitor/unexecuted_indirect.py').read_text()
    assert 'indirect_guard_binding' in monitor and 'delivery=\'lossless\'' in monitor


def test_pure_helpers_are_kept_out_of_production_import_dependencies():
    for family in ('indirect_path', 'conditional_prefix'):
        text = Path('testbenches/bpu/tests/scoreboard/_' + family + '_program.py').read_text()
        assert 'sys.path' not in text and '__main__' not in text
    from suites.frontend.bpu.testbenches.shared.env.pytest_plugins.isolation import item_scope
    from types import SimpleNamespace
    item = SimpleNamespace(nodeid='testbenches/bpu/tests/scoreboard/test_conditional_prefix.py::test_synthetic',
        fixturenames=(), iter_markers=lambda name: ())
    assert item_scope(item) == 'pure'
