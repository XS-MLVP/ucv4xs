"""Structural checks must not disguise pin aliases as transaction migration."""
import functools
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'audit_suite_layout', ROOT / 'scripts/audit-suite-layout.py')
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


@functools.lru_cache(maxsize=1)
def audit_rows():
    return tuple(AUDIT.audit(*entry) for entry in AUDIT.suite_entries())


def test_every_suite_passes_the_layout_contract():
    problems = {row['suite']: AUDIT.violations(row) for row in audit_rows()}
    assert not {suite: rows for suite, rows in problems.items() if rows}, problems


def test_layout_audit_sees_every_registered_suite():
    assert {row['suite'] for row in audit_rows()} == {
        'bpu', 'ftq', 'icache', 'ifu', 'ibuffer', 'instr_uncache', 'dcache',
        'lsq', 'lsu', 'mmu', 'sbuffer', 'vagq',
    }


def test_owner_discovery_follows_registered_plugins_without_importing_them(tmp_path, monkeypatch):
    monkeypatch.setattr(AUDIT, 'ROOT', tmp_path)
    root = tmp_path / 'conftest.py'
    root.write_text('pytest_plugins = ("fixtures_a", "missing_plugin")\n')
    (tmp_path / 'fixtures_a.py').write_text('''raise RuntimeError("must not import")
pytest_plugins = ["fixtures_b"]
@pytest.fixture
def cache_agent(): pass
''')
    (tmp_path / 'fixtures_b.py').write_text('''pytest_plugins = "fixtures_a"
@pytest.fixture
def queue_env(): pass
''')
    (tmp_path / 'unregistered.py').write_text('@pytest.fixture\ndef stray_dut(): pass\n')
    assert AUDIT.root_fixtures(root) == {'cache_agent', 'queue_env'}


@pytest.mark.parametrize('suite', ['bpu', 'ftq', 'icache', 'ifu', 'ibuffer',
                                   'instr_uncache',
                                   'dcache', 'lsq', 'lsu', 'mmu', 'sbuffer', 'vagq'])
def test_audit_separates_structure_from_transaction_boundary(suite):
    """Report current debt without requiring it to remain in future code."""
    row = next(row for row in audit_rows() if row['suite'] == suite)
    assert AUDIT.violations(row) == []
    assert row['pin_fields'] == sum(
        fields['literal'] + fields['keyword'] + fields['alias']
        for fields in row['pin_level_cases'])
    coupling=bool(row['pin_fields'] or row['signal_operations'] or row['component_accesses'])
    expected = 'needs-adapter' if coupling else 'no-static-leak-found'
    assert row['transaction_boundary'] == expected
    assert bool(AUDIT.violations(row, require_transaction_boundary=True)) == coupling


def test_raw_handles_and_signal_dictionaries_cannot_evade_transaction_audit(tmp_path):
    path=tmp_path/'test_example.py'
    path.write_text('''def test_example(env):
    env.channels[0]['d_valid'].Set(1)
    return env.raw_dut.xport.GetKeys()
''')
    hits=AUDIT.signal_accesses(path)
    assert {(hit['kind'],hit['expression']) for hit in hits}=={
        ('signal-operation',"env.channels[0]['d_valid'].Set"),
        ('signal-operation','env.raw_dut.xport.GetKeys'),
        ('native-handle','env.raw_dut'),('native-handle','env.raw_dut.xport')}


def test_transaction_audit_does_not_misclassify_a_plain_response_value(tmp_path):
    path=tmp_path/'test_example.py'
    path.write_text('def test_example(agent):\n    assert agent.response.value == 7\n')
    assert AUDIT.signal_accesses(path)==[]


def test_explicit_selfchecks_keep_mixed_features_and_helpers_in_the_audit(tmp_path, monkeypatch):
    suite = tmp_path / 'suite'
    tests = suite / 'tests'
    tests.mkdir(parents=True)
    (suite / '__init__.py').write_text('')
    (suite / 'conftest.py').write_text('agent = agent_fixture()\n')
    (suite / 'pytest.ini').write_text('[pytest]\nmarkers =\n    selftest: framework controls\n')
    (tests / 'test_encoding.py').write_text('''import pytest
from example.legacy_pins import P as fields
pytestmark = [pytest.mark.selftest, pytest.mark.toffee_functional_coverage(False)]
def test_encoding():
    assert encode()[fields.p_valid] == 1
''')
    (tests / 'test_mixed.py').write_text('''import pytest
from example.legacy_pins import P as fields
@pytest.mark.selftest
def test_bad_field():
    encode(fields.p_unknown)
def helper(env):
    env.raw_dut.Step(1)
@pytest.mark.toffee_functional_coverage(False)
def test_feature(env):
    env.ports.read()
class TestMixed:
    @pytest.mark.selftest(reason="encoding contract")
    def test_encoding(self):
        assert encode()[fields.p_valid] == 1
    def test_feature(self, env):
        env.read_driver.send({})
''')
    monkeypatch.setattr(AUDIT, 'ROOT', tmp_path)
    row = AUDIT.audit('example', suite, suite, tests)
    assert row['transaction_boundary'] == 'needs-adapter'
    assert row['pin_fields'] == 0
    assert row['signal_operations'] == 2  # helper's raw handle and Step
    assert row['component_accesses'] == 2
    assert len(row['selftest_cases']) == 2
    assert sum(case['pin_fields']['alias'] for case in row['selftest_cases']) == 3
    assert {item['scope'] for case in row['selftest_cases'] for item in case['classifications']} == {
        '<module>', 'test_bad_field', 'TestMixed.test_encoding'}
    assert AUDIT.violations(row, require_transaction_boundary=True)


def test_dynamic_or_reassigned_selftest_markers_do_not_hide_pin_access(tmp_path):
    for marker in (
        'pytestmark = pytest.mark.selftest if enabled else []',
        'pytestmark = pytest.mark.selftest\npytestmark = []',
        'pytestmark = [pytest.mark.selftest]\npytestmark.clear()',
        'pytestmark = [pytest.mark.selftest]\nalias = pytestmark\nalias.clear()',
        'pytestmark = pytest.mark.selftest\ndel pytestmark',
        'if enabled:\n    pytestmark = pytest.mark.selftest',
        'pytestmark = pytest.mark.toffee_functional_coverage(False)',
    ):
        path = tmp_path / 'test_example.py'
        path.write_text(marker + '\ndef test_feature(env):\n    env.raw_dut.Step(1)\n')
        tree, controls, classifications = AUDIT.selftest_scopes(AUDIT.source_tree(path))
        assert not controls.body and not classifications
        assert len(AUDIT.signal_accesses(tree)) == 2


@pytest.mark.parametrize('body', [
    "agent.read_driver.set({'valid': 1})",
    "agent.write_driver.send({'valid': 1})",
    "agent.ports.read.bits.sample()",
    "agent.model.write(3, 15, 7)",
    "agent.model.sets",
    "agent.prediction_monitor.sample_at(event)",
    "agent._encode_read(3)",
    "agent._edge()",
    "other = cache_agent; other.flush_driver.set({'flush': 1})",
    "writer = env.read_driver; writer.set({'valid': 1})",
])
def test_functional_component_bypass_is_not_a_clean_transaction_boundary(tmp_path, monkeypatch, body):
    """Renaming pins to logical keys or reaching the model is not migration."""
    suite=tmp_path/'suites'/'frontend'/'example'
    tests=suite/'tests'
    tests.mkdir(parents=True)
    (suite/'__init__.py').write_text('')
    (suite/'pytest.ini').write_text('[pytest]\nmarkers =\n    selftest: framework controls\n')
    (suite/'conftest.py').write_text('cache_agent = agent_fixture()\n')
    (tests/'test_feature.py').write_text('def test_feature(agent, cache_agent, env, event):\n    '+body+'\n')
    monkeypatch.setattr(AUDIT, 'ROOT', tmp_path)
    row=AUDIT.audit('example',suite,suite,tests)
    assert AUDIT.violations(row)==[]
    assert row['pin_fields']==row['signal_operations']==0
    assert row['transaction_boundary']=='needs-adapter'
    assert AUDIT.violations(row,require_transaction_boundary=True)


@pytest.mark.parametrize('body',[
    'actual = agent.response.value',
    'response = agent.read(3); response.model',
    'reference = ReferenceModel(); reference.write(3, 15, 7)',
    "description = 'agent.ports io_documentation_only'",
])
def test_owner_component_guard_keeps_transactions_and_independent_oracles_legal(tmp_path,body):
    path=tmp_path/'test_legal.py'
    path.write_text('def test_feature(agent):\n    '+body+'\n')
    assert AUDIT.component_accesses(path)==[]


def test_owner_component_guard_sees_constant_getattr_and_aliases_without_counting_prose(tmp_path):
    path=tmp_path/'test_example.py'
    path.write_text('''"""agent.ports is prohibited, but this is prose."""
def test_feature(cache_agent):
    alias = cache_agent
    getattr(alias, 'read_driver').set({'valid': 1})
''')
    assert AUDIT.component_accesses(path)==[dict(line=4,kind='owner-component',
        expression="getattr(alias, 'read_driver')")]


def test_sbuffer_functional_tests_remain_transaction_only():
    row = next(row for row in audit_rows() if row['suite'] == 'sbuffer')
    assert AUDIT.violations(row, require_transaction_boundary=True) == []


def test_store_delay_case_cannot_bypass_its_transaction_runtime():
    path = ROOT / 'suites/memblock/lsu/testbenches/store_delay/tests/test_store_delay.py'
    assert AUDIT.signal_accesses(path) == []
    assert AUDIT.native_access(path) == []
    assert not any(AUDIT.pin_accesses(path).values())


def test_ifu_perf_analysis_case_uses_only_semantic_transactions():
    path = ROOT / 'suites/frontend/ifu/testbenches/perf_analysis/tests/test_perf_analysis.py'
    assert AUDIT.signal_accesses(path) == []
    assert AUDIT.native_access(path) == []
    assert not any(AUDIT.pin_accesses(path).values())


def test_ifu_pred_checker_case_uses_only_semantic_transactions():
    path = ROOT / 'suites/frontend/ifu/testbenches/pred_checker/tests/test_pred_checker.py'
    assert AUDIT.signal_accesses(path) == []
    assert AUDIT.native_access(path) == []
    assert not any(AUDIT.pin_accesses(path).values())


def test_ifu_rvc_expander_case_uses_only_semantic_transactions():
    path = ROOT / 'suites/frontend/ifu/testbenches/rvc_expander/tests/test_rvc_expander.py'
    assert AUDIT.signal_accesses(path) == []
    assert AUDIT.native_access(path) == []
    assert not any(AUDIT.pin_accesses(path).values())


def test_ifu_instr_boundary_case_uses_only_semantic_transactions():
    path = ROOT / 'suites/frontend/ifu/testbenches/instr_boundary/tests/test_instr_boundary.py'
    assert AUDIT.signal_accesses(path) == []
    assert AUDIT.native_access(path) == []
    assert not any(AUDIT.pin_accesses(path).values())


def test_ifu_frontend_trigger_case_uses_only_semantic_transactions():
    path = ROOT / 'suites/frontend/ifu/testbenches/frontend_trigger/tests/test_frontend_trigger.py'
    assert AUDIT.signal_accesses(path) == []
    assert AUDIT.native_access(path) == []
    assert not any(AUDIT.pin_accesses(path).values())


def test_ifu_uncache_case_uses_only_semantic_transactions():
    path = ROOT / 'suites/frontend/ifu/testbenches/uncache_unit/tests/test_uncache_unit.py'
    assert AUDIT.signal_accesses(path) == []
    assert AUDIT.native_access(path) == []
    assert not any(AUDIT.pin_accesses(path).values())


def test_selftest_marker_is_registered_by_every_suite():
    for row in audit_rows():
        assert row['selftest_marker'], row['suite']


@pytest.mark.parametrize('module',['example.common.pins','example.legacy_pins'])
def test_pin_aliases_and_keywords_cannot_evade_audit(tmp_path,module):
    path = tmp_path / 'test_example.py'
    path.write_text(f'from {module} import P as fields'+chr(10)+'''
def test_example(env):
    env.set(io_req_valid=1)
    env.expect({fields.p_req_ready: 1})
    env.read(fields.io(f"response_{0}_valid"))
''')
    assert AUDIT.pin_accesses(path) == {'literal': 0, 'keyword': 1, 'alias': 2}


def test_namespace_audit_rejects_legacy_imports_but_preserves_history(tmp_path):
    (tmp_path/'__init__.py').write_text('')
    (tmp_path/'native.py').write_text('from lsqverify.native import Native'+chr(10))
    (tmp_path/'history.py').write_text('frozen = "lsqverify/native.py"'+chr(10))
    issues=AUDIT.namespace_problems(tmp_path)
    assert len(issues)==1 and 'nonqualified import lsqverify.native' in issues[0]
    (tmp_path/'common').mkdir()
    assert 'obsolete implementation wrapper: common' in AUDIT.namespace_problems(tmp_path)


def test_pin_audit_ignores_prose_not_executable_fields(tmp_path):
    path = tmp_path / 'test_example.py'
    path.write_text('''"""io_documentation_only"""
def test_example(env):
    env.read("io_req_ready")
''')
    assert AUDIT.pin_accesses(path) == {'literal': 1, 'keyword': 0, 'alias': 0}


@pytest.mark.parametrize('suite', ['dcache', 'lsu', 'mmu', 'sbuffer'])
def test_moved_fixture_root_still_resolves_suite_directory(suite):
    import ast
    path = ROOT / 'suites' / 'memblock' / suite / 'conftest.py'
    tree = ast.parse(path.read_text())
    expr = next(node.value for node in tree.body if isinstance(node, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == 'ROOT' for t in node.targets))
    actual = eval(compile(ast.Expression(expr), str(path), 'eval'),
                  {'Path': Path, '__file__': str(path)})
    assert actual == path.parent
