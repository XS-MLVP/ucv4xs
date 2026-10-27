"""Keep DUT ownership and component responsibilities visible in the layout."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DUTS = ('abtb', 'bpu', 'ittage', 'mbtb', 'ras', 'sc', 'tage', 'ubtb', 'uras', 'utage')


def test_verification_root_only_contains_package_initializer():
    assert {path.name for path in (ROOT / 'bpuverify').glob('*.py')} == {'__init__.py'}
    tree = ast.parse((ROOT / 'bpuverify/__init__.py').read_text())
    assert not any(isinstance(node, (ast.Import, ast.ImportFrom)) for node in tree.body)


def test_each_dut_owns_real_agent_bundle_and_environment_implementations():
    for dut in DUTS:
        package = ROOT / 'bpuverify' / dut
        for role, leaf, expected in (('agent', 'main.py', ast.ClassDef),
                                     ('bundle', 'ports.py', ast.ClassDef)):
            tree = ast.parse((package / role / leaf).read_text())
            assert any(isinstance(node, expected) for node in tree.body), (dut, role)
        assert (package / 'env/pytest.py').is_file()
        assert (package / 'case').is_dir()
        assert (package / 'transaction/types.py').is_file()


def test_testcase_directories_do_not_hold_reusable_support_modules():
    for dut in DUTS:
        helpers = [path.name for path in (ROOT / 'tests' / dut / 'testcase').glob('*.py')
                   if path.name != '__init__.py' and not path.name.startswith('test_')]
        assert not helpers, (dut, helpers)


def test_conftest_files_only_register_fixtures_and_plugins():
    for path in [ROOT / 'tests/conftest.py', *(ROOT / 'tests' / dut / 'conftest.py' for dut in DUTS)]:
        tree = ast.parse(path.read_text())
        assert not any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                       for node in tree.body), path


def test_legacy_packages_and_interface_directories_are_absent():
    for name in ('integrated', 'abtb_state', 'bpu_sc_state'):
        assert not (ROOT / 'bpuverify' / name).exists()
    assert not list((ROOT / 'tests').glob('*/interfaces'))
    assert not (ROOT / 'tests/support').exists()


def test_integrated_components_are_under_bpu_roles_not_a_separate_dut():
    for role, group in (('model', 'abtb'), ('monitor', 'abtb'), ('checker', 'abtb'),
                        ('env', 'abtb'), ('case', 'abtb'), ('coverage', 'abtb'),
                        ('model', 'sc'), ('monitor', 'sc'), ('checker', 'sc'),
                        ('model', 'bypass'), ('monitor', 'bypass'), ('checker', 'bypass')):
        assert (ROOT / 'bpuverify/bpu' / role / group).is_dir(), (role, group)
