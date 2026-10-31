"""Keep DUT ownership and component responsibilities visible in the layout.

The ICache project is split into one directory per DUT so that a change to an
outer adapter or to a sibling subblock cannot silently reshape another DUT's
test surface. The whole-ICache DUT is a peer of its subblocks, not their parent.
"""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DUTS = (
    'waylookup', 'replacer', 'mshr', 'databank', 'metabank', 'metaarray',
    'dataarray', 'missunit', 'mainpipe', 'prefetchpipe', 'icache',
)
ROLES = ('agent', 'bundle', 'transaction', 'case')

# DUTs with real agent/model/checker implementations; empty env role directories
# are deliberately not required.
IMPLEMENTED = ('waylookup', 'replacer', 'mshr', 'missunit', 'mainpipe',
               'prefetchpipe', 'databank', 'metabank', 'metaarray',
               'dataarray', 'icache')


def test_verification_root_only_contains_package_initializer():
    assert {path.name for path in ROOT.glob('*.py')} == {'__init__.py', 'bist.py'}
    tree = ast.parse((ROOT / '__init__.py').read_text())
    # ``from __future__ import annotations`` is a compiler directive, not a
    # re-export table.
    imports = [
        node for node in tree.body
        if isinstance(node, (ast.Import, ast.ImportFrom))
        and not (isinstance(node, ast.ImportFrom) and node.module in {'__future__', 'pathlib'})
    ]
    assert not imports, "verification root must not re-export DUT symbols"
    assert not (ROOT / 'icacheverify').exists()


def test_each_dut_owns_a_package_directory():
    for dut in DUTS:
        assert (ROOT / dut).is_dir(), dut


def test_each_dut_has_the_role_directories():
    for dut in DUTS:
        package = ROOT / dut
        for role in ROLES:
            assert (package / role).is_dir(), (dut, role)
        assert (package / '__init__.py').is_file(), dut


def test_implemented_duts_declare_bundle_transaction_and_environment():
    for dut in IMPLEMENTED:
        package = ROOT / dut
        for role, leaf, expected in (
            ('bundle', 'ports.py', ast.ClassDef),
            ('agent', 'main.py', ast.ClassDef),
        ):
            path = package / role / leaf
            assert path.is_file(), (dut, role)
            tree = ast.parse(path.read_text())
            assert any(isinstance(node, expected) for node in tree.body), (dut, role)
        assert (package / 'transaction/types.py').is_file(), dut
        assert (package / 'case').is_dir(), dut


def test_testcase_directories_do_not_hold_reusable_support_modules():
    for dut in IMPLEMENTED:
        case_dir = ROOT / 'tests' / dut / 'testcase'
        if not case_dir.is_dir():
            continue
        helpers = [
            path.name for path in case_dir.glob('*.py')
            if path.name != '__init__.py' and not path.name.startswith('test_')
        ]
        assert not helpers, (dut, helpers)


def test_each_dut_fixture_is_declared_once_at_the_pytest_root():
    tree = ast.parse((ROOT / 'tests/conftest.py').read_text())
    fixtures = {
        target.id
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name) and target.id.endswith('_agent')
    }
    assert fixtures == {f'{dut}_agent' for dut in DUTS}
    assert not list((ROOT).glob('*/env/pytest.py'))
    assert not list((ROOT / 'tests').glob('*/conftest.py'))
    assert not any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        for node in tree.body
    )


def test_functional_testcases_only_use_agent_transaction_apis():
    offenders = []
    for path in (ROOT / 'tests').glob('*/testcase/*.py'):
        text = path.read_text()
        for token in ('.dut.', '.pins.'):
            if token in text:
                offenders.append(f'{path.relative_to(ROOT)} contains {token}')
    assert not offenders, offenders


def test_each_dut_has_a_minimal_rtl_closure():
    """A DUT must not be built from the whole SoC RTL dump."""
    for dut in DUTS:
        directory = ROOT / 'rtl' / dut
        listing = directory / 'filelist.f'
        assert listing.is_file(), dut
        files = [line for line in listing.read_text().split() if line.strip()]
        assert files, dut
        assert len(files) < 100, (dut, len(files))
        for name in files:
            assert (directory / name).is_file(), (dut, name)


def test_whole_icache_is_a_peer_of_its_subblocks():
    """The integration DUT is not allowed to own subblock test components."""
    assert (ROOT / 'icache').is_dir()
    for dut in DUTS:
        if dut == 'icache':
            continue
        assert not (ROOT / 'icache' / dut).exists(), dut
