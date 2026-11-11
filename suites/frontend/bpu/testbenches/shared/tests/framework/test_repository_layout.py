"""Keep DUT ownership and component responsibilities visible in the layout."""
import ast
from pathlib import Path

ROOT = __import__('suites.frontend.bpu', fromlist=['ROOT']).ROOT
DUTS = ('abtb', 'bpu', 'ittage', 'mbtb', 'ras', 'sc', 'tage', 'ubtb', 'uras', 'utage')


def test_verification_root_only_contains_package_initializer():
    assert {path.name for path in ROOT.glob('*.py')} == {'__init__.py', 'conftest.py'}
    tree = ast.parse((ROOT / '__init__.py').read_text())
    imports = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]
    assert all(isinstance(node, ast.ImportFrom) and node.module == 'pathlib' for node in imports)
    assert not (ROOT / 'bpuverify').exists()


def test_each_dut_owns_real_agent_bundle_and_environment_implementations():
    for dut in DUTS:
        package = ROOT / 'testbenches' / dut
        for role, leaf, expected in (('agent', 'main.py', ast.ClassDef),
                                     ('bundle', 'ports.py', ast.ClassDef)):
            tree = ast.parse((package / 'env' / role / leaf).read_text())
            assert any(isinstance(node, expected) for node in tree.body), (dut, role)
        assert (package / 'tests/scenarios').is_dir()
        assert (package / 'transactions/types.py').is_file()


def test_each_dut_fixture_is_declared_once_at_the_pytest_root():
    source = (ROOT / 'conftest.py').read_text()
    tree = ast.parse(source)
    fixtures = {
        target.id
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name) and target.id.endswith('_agent')
    }
    assert fixtures == {f'{dut}_agent' for dut in DUTS} | {'mbtb_cleanup_agent'}
    assert not list((ROOT / 'testbenches').rglob('env/pytest.py'))
    assert not list((ROOT / 'testbenches').rglob('conftest.py'))


def test_testcase_directories_do_not_hold_reusable_support_modules():
    for dut in DUTS:
        helpers = [path.name for path in (ROOT / 'testbenches' / dut / 'tests/testcase').glob('*.py')
                   if path.name != '__init__.py' and not path.name.startswith('test_')]
        assert not helpers, (dut, helpers)


def test_root_conftest_has_no_inline_fixture_functions():
    path = ROOT / 'conftest.py'
    tree = ast.parse(path.read_text())
    assert not any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                   for node in tree.body), path


def test_legacy_packages_and_interface_directories_are_absent():
    for name in ('integrated', 'abtb_state', 'bpu_sc_state'):
        assert not (ROOT / name).exists()
    assert not list((ROOT / 'testbenches').glob('*/interfaces'))
    assert not (ROOT / 'tests/support').exists()


def test_functional_testcases_only_use_agent_transaction_apis():
    offenders = []
    paths=list((ROOT / 'testbenches').glob('*/tests/testcase/*.py'))
    assert paths, 'functional scan must include module testcases'
    for path in paths:
        text = path.read_text()
        for token in ('.dut.', '.pins.'):
            if token in text:
                offenders.append(f"{path.relative_to(ROOT)} contains {token}")
    assert not offenders, offenders


def test_integrated_components_are_under_bpu_roles_not_a_separate_dut():
    for role, group in (('model', 'abtb'), ('monitor', 'abtb'), ('checker', 'abtb'),
                        ('env', 'abtb'), ('case', 'abtb'), ('coverage', 'abtb'),
                        ('model', 'sc'), ('monitor', 'sc'), ('checker', 'sc'),
                        ('model', 'bypass'), ('monitor', 'bypass'), ('checker', 'bypass')):
        prefix={'monitor':'env/monitor','env':'tests/scenarios/lifetimes','case':'tests/scenarios'}.get(role,role)
        assert (ROOT / 'testbenches/bpu' / prefix / group).is_dir(), (role, group)
