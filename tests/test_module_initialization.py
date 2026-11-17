"""Persistent module identities must not merge per-DUT workspaces. MPL-2.0."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from ucv import modules
from ucv.cli import main
from ucv.common import UcvError, digest, file_hash, read, write
from ucv.config import Project
from ucv.documents import refresh_index, refresh_work_index
from ucv.layout import refresh_readmes
from ucv.workspace import check, info, initialize, markdown, metadata
from ucv.workspace import test_roots as selected_test_roots


CATALOG = 'docs/module-catalog.json'
FAMILY = 'demo.pipeline'
CONTROL = 'demo.control'
FAMILY_NAME = '流水线模块族'


@pytest.fixture
def project(tmp_path):
    """An existing schema2 suite; never read the checkout's adoption data."""
    write(tmp_path/'ucv.json', {
        'baseline': 'test', 'suites': {'demo': 'suites/frontend/demo'},
        'profiles': {'public': ['demo']},
    })
    write(tmp_path/'dependencies/versions.json', {})
    write(tmp_path/'baselines/test.json', {
        'name': 'test', 'repository': 'https://example.test/repo.git',
        'commit': 'a'*40, 'visibility': 'public', 'recursive_submodules': [],
        'patches': [], 'firtool_options': [],
        'design': {'top': 'top.TopMain', 'config': 'DefaultConfig',
                   'num_cores': 1, 'chisel_args': []},
        'tools': {'mill': '1', 'chisel': '2', 'firtool': '3', 'java': '17'},
    })
    root = tmp_path/'suites/frontend/demo'
    write(root/'ucv.json', {
        'suite': 'demo', 'generation': 'soc', 'pytest_root': '.',
        'tests': ['testbenches'], 'duts': {
            'one': {'top': 'One', 'export_name': 'OneDut'},
            'two': {'top': 'Two', 'export_name': 'TwoDut'},
        },
    })
    for directory in (tmp_path/'suites', root.parent, root, root/'testbenches'):
        directory.mkdir(parents=True, exist_ok=True)
        (directory/'__init__.py').write_text('')
    (root/'conftest.py').write_bytes(b'# Retained fixture registration.\r\n')
    (root/'pytest.ini').write_text('[pytest]\ntestpaths = testbenches\n')
    (root/'README.md').write_bytes(b'# Existing suite\r\n\r\nOwner notes.  \r\n')
    meta = {'schema': 2, 'fixtures': 'conftest.py', 'duts': {}}
    for dut in ('one', 'two'):
        base = root/'testbenches'/dut
        (base/'tests').mkdir(parents=True)
        (base/'__init__.py').write_text('')
        (base/'tests/__init__.py').write_text('')
        (base/'env.py').write_bytes(
            f'"""User-owned {dut} environment."""\r\nOWNER = "{dut}"  \r\n'.encode())
        smoke = f'testbenches/{dut}/tests/test_{dut}_contract.py::test_contract'
        (root/smoke.split('::')[0]).write_text(
            'def test_contract():\n'
            '    raise NotImplementedError("synthetic fixture has no hardware")\n')
        for role in ('design', 'verification'):
            path = root/f'docs/spec/{role}/{dut}.md'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(f'# Retained {dut} {role} contract\r\n\r\nOwner evidence.  \r\n'.encode())
        meta['duts'][dut] = {
            'testbench': dut, 'environment': f'testbenches/{dut}/env.py',
            'tests': [f'testbenches/{dut}/tests'], 'smoke': smoke,
            'design_spec': f'docs/spec/design/{dut}.md',
            'verification_spec': f'docs/spec/verification/{dut}.md',
            'binding': {'observed_baseline': 'test', 'observed_top': dut.title(),
                        'availability': 'present', 'verification_state': 'existing-unrevalidated'},
        }
    pages = ['docs/README.md', 'docs/spec/design/README.md',
             'docs/spec/verification/README.md', 'docs/bugs/README.md']
    for name in pages:
        path = root/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('# Existing documentation\n\nRetained owner notes.\n')
    for state in ('open', 'closed'):
        (root/'docs/bugs'/state).mkdir()
    write(root/'workspace.json', meta)
    write(root/'docs/navigation.json', {'schema': 1, 'current': ['README.md', *pages]})
    result = Project(tmp_path)
    suite = result.suite('demo')
    refresh_readmes(result, suite, meta, write=True)
    refresh_index(result, suite, write=True)
    refresh_work_index(result, suite, meta, write=True)
    return result


@pytest.fixture
def adoption(project):
    evidence = project.root/'docs/fixture-observation.json'
    write(evidence, {'synthetic': True, 'tops': ['One', 'Two', 'Three', 'Four']})
    baseline = project.suite('demo').baseline
    rows = []
    for mid, name, tops in ((FAMILY, FAMILY_NAME, ['One', 'Three', 'Four']),
                            (CONTROL, '控制模块', ['Two'])):
        rows.append({
            'module_id': mid, 'scope': 'fixture', 'name': name, 'parent_id': None,
            'lifecycle': 'active', 'aliases': [], 'references': [],
            'tracking': {'owner': 'fixture-owner', 'task': 'retain-this-task'},
            'history': [], 'observations': [{
                'baseline': baseline['name'], 'baseline_sha256': digest(baseline),
                'availability': 'present', 'source': None, 'rtl_tops': tops,
                'evidence': ['fixture'],
            }],
        })
    return {
        'catalog': {'schema': 1, 'modules': rows, 'evidence': {
            'fixture': {'reference': str(evidence.relative_to(project.root)),
                        'sha256': file_hash(evidence)},
        }},
        'dut_modules': {'demo': {'one': FAMILY, 'two': CONTROL}},
    }


def tree_state(root):
    """Include bytes, empty directories and links, excluding advisory locks."""
    result = {}
    for path in root.rglob('*'):
        relative = path.relative_to(root)
        if relative.parts[:2] == ('.cache', 'locks'):
            continue
        if path.is_symlink():
            result[relative] = ('symlink', path.readlink())
        elif path.is_file():
            result[relative] = ('file', path.read_bytes())
        else:
            result[relative] = ('directory', None)
    return result


def init_arguments(project, dut, top, module_id):
    args = ['--root', str(project.root), 'init', 'demo', '--group', 'frontend',
            '--dut', dut, '--top', top, '--export-name', top+'Dut']
    if module_id is not None:
        args += ['--module-id', module_id]
    return args


def test_adopt_persists_each_dut_identity_and_preserves_existing_bytes(project, adoption):
    suite = project.suite('demo')
    original_meta = metadata(suite)
    original_snapshot = deepcopy(adoption)
    before = tree_state(project.root)
    mutable = {Path('ucv.json'), suite.path.relative_to(project.root)/'workspace.json'}
    hashes = {str(path): hashlib.sha256(before[path][1]).hexdigest() for path in mutable}

    result = modules.adopt(project, adoption, CATALOG)

    assert result['status'] == 'ADOPTED' and result['errors'] == []
    assert result['modules'] == 2 and result['duts'] == 2
    assert result['catalog_sha256'] == digest(adoption['catalog'])
    assert result['previous_file_hashes'] == hashes
    reloaded = Project(project.root)
    assert reloaded.config['modules'] == CATALOG
    assert modules.load(reloaded) == adoption['catalog']
    expected = deepcopy(original_meta)
    for dut, mid in adoption['dut_modules']['demo'].items():
        expected['duts'][dut]['module_id'] = mid
    assert metadata(reloaded.suite('demo')) == expected
    assert adoption == original_snapshot
    after = tree_state(project.root)
    for path, value in before.items():
        if path not in mutable:
            assert after[path] == value, path
    assert modules.check(reloaded)['errors'] == []
    assert check(reloaded, [reloaded.suite('demo')])['errors'] == []


@pytest.mark.parametrize('missing', ['suite', 'dut'])
def test_adopt_requires_complete_per_dut_mapping(project, adoption, missing):
    if missing == 'suite':
        del adoption['dut_modules']['demo']
    else:
        del adoption['dut_modules']['demo']['two']
    before = tree_state(project.root)
    with pytest.raises(UcvError, match='adoption must account for every'):
        modules.adopt(project, adoption, CATALOG)
    assert tree_state(project.root) == before
    assert 'modules' not in project.config


@pytest.mark.parametrize('invalid', ['unknown-id', 'baseline-name', 'baseline-hash', 'top'])
def test_adopt_rejects_incompatible_bindings_before_writing(project, adoption, invalid):
    # Fail the second DUT after the first has passed validation.
    observed = adoption['catalog']['modules'][1]['observations'][-1]
    if invalid == 'unknown-id':
        adoption['dut_modules']['demo']['two'] = 'unknown.module'
        message = 'unknown adopted identity'
    else:
        field, value = {
            'baseline-name': ('baseline', 'other'),
            'baseline-hash': ('baseline_sha256', 'b'*64),
            'top': ('rtl_tops', ['Unrelated']),
        }[invalid]
        observed[field] = value
        message = 'adopted DUT disagrees with baseline/module: demo/two'
    before = tree_state(project.root)
    with pytest.raises(UcvError, match=message):
        modules.adopt(project, adoption, CATALOG)
    assert tree_state(project.root) == before
    assert 'modules' not in project.config


@pytest.mark.parametrize('existing', ['catalog-file', 'catalog-directory', 'catalog-symlink',
                                     'configured-catalog', 'dut-identity'])
def test_adopt_refuses_to_overwrite_catalogs_or_identities(project, adoption, existing):
    destination = CATALOG
    path = project.root/destination
    message = 'refusing to overwrite catalog'
    if existing == 'catalog-file':
        path.write_bytes(b'Owner data; not an adoption target.\r\n')
    elif existing == 'catalog-directory':
        path.mkdir()
        (path/'owner.txt').write_bytes(b'Retain directory contents.\n')
    elif existing == 'catalog-symlink':
        path.symlink_to('missing-owner-catalog.json')
    elif existing == 'configured-catalog':
        modules.adopt(project, adoption, destination)
        destination = 'docs/replacement.json'
        message = 'catalog already configured'
    else:
        workspace = project.suite('demo').path/'workspace.json'
        meta = read(workspace)
        meta['duts']['two']['module_id'] = FAMILY
        write(workspace, meta)
        message = 'refusing to replace an existing DUT identity'
    before = tree_state(project.root)
    config = deepcopy(project.config)
    with pytest.raises(UcvError, match=message):
        modules.adopt(project, adoption, destination)
    assert tree_state(project.root) == before
    assert project.config == config


def test_adopt_rolls_back_original_bytes_when_readback_rejects_a_reference(project, adoption):
    adoption['catalog']['modules'][1]['references'] = ['docs/missing-contract.md']
    before = tree_state(project.root)
    config = deepcopy(project.config)
    with pytest.raises(UcvError, match='adoption readback: .*missing reference'):
        modules.adopt(project, adoption, CATALOG)
    assert tree_state(project.root) == before
    assert project.config == config
    assert not (project.root/CATALOG).exists()


def test_same_module_id_creates_independent_dut_implementations(project, adoption):
    modules.adopt(project, adoption, CATALOG)
    root = project.suite('demo').path
    before = tree_state(project.root)
    old_meta = metadata(project.suite('demo'))
    suite_relative = root.relative_to(project.root)
    mutable = {suite_relative/name for name in (
        'ucv.json', 'workspace.json', 'docs/navigation.json', 'docs/spec/verification/README.md')}

    assert initialize(project, 'demo', 'frontend', 'three', 'Three', 'ThreeDut', FAMILY) == str(root)
    reloaded = Project(project.root)
    assert initialize(reloaded, 'demo', 'frontend', 'four', 'Four', 'FourDut', FAMILY) == str(root)
    suite = reloaded.suite('demo')
    meta = metadata(suite)
    smoke_nodes = []
    for dut in ('three', 'four'):
        entry = meta['duts'][dut]
        base = root/'testbenches'/dut
        assert entry['module_id'] == FAMILY
        assert entry['testbench'] == dut
        assert entry['environment'] == f'testbenches/{dut}/env.py'
        assert entry['tests'] == [f'testbenches/{dut}/tests']
        assert entry['smoke'] == f'testbenches/{dut}/tests/test_{dut}_smoke.py::test_smoke'
        for name in ('__init__.py', 'env.py', 'transactions.py', 'README.md',
                     'tests/__init__.py', f'tests/test_{dut}_smoke.py'):
            assert (base/name).is_file() and not (base/name).is_symlink()
        assert selected_test_roots(suite, [dut]) == [base/'tests']
        smoke_nodes.append(entry['smoke'])
    assert not (root/'testbenches/three/env.py').samefile(root/'testbenches/four/env.py')
    assert selected_test_roots(suite, ['three', 'four']) == [
        root/'testbenches/three/tests', root/'testbenches/four/tests']
    assert selected_test_roots(suite, ['one']) == [root/'testbenches/one/tests']
    for dut, entry in old_meta['duts'].items():
        assert meta['duts'][dut] == entry
    after = tree_state(project.root)
    for path, value in before.items():
        if path not in mutable:
            assert after[path] == value, path
    assert check(reloaded, [suite])['errors'] == []

    # A structural PASS is not a smoke PASS: execute the generated placeholders
    # unchanged and require two real failures, with no native DUT involved.
    env = {**os.environ, 'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1',
           'PYTHONDONTWRITEBYTECODE': '1', 'PYTEST_ADDOPTS': ''}
    result = subprocess.run(
        [sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', '-o', 'addopts=', *smoke_nodes],
        cwd=root, env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 1, result.stdout+result.stderr
    assert '2 failed' in result.stdout, result.stdout+result.stderr
    assert 'TODO: register the DUT fixture and implement the smoke contract' in result.stdout


def test_existing_suite_without_catalog_allows_initialization_without_identity(project):
    initialize(project, 'demo', 'frontend', 'three', 'Three', 'ThreeDut')
    suite = project.suite('demo')
    assert 'modules' not in Project(project.root).config
    assert 'module_id' not in metadata(suite)['duts']['three']
    assert selected_test_roots(suite, ['three']) == [suite.path/'testbenches/three/tests']
    assert check(project, [suite])['errors'] == []


@pytest.mark.parametrize('via_cli', [False, True], ids=['api', 'cli'])
@pytest.mark.parametrize('invalid', ['missing-id', 'unknown-id', 'top', 'absent',
                                    'unobserved', 'baseline-name', 'baseline-hash'])
def test_init_rejects_invalid_identity_without_new_skeleton(project, adoption, invalid, via_cli, capsys):
    modules.adopt(project, adoption, CATALOG)
    module_id, top = FAMILY, 'Three'
    if invalid in {'missing-id', 'unknown-id'}:
        module_id = None if invalid == 'missing-id' else 'unknown.module'
        message = 'init requires an existing --module-id'
    elif invalid == 'top':
        top = 'Unrelated'
        message = 'new DUT top must belong to the observed module variants'
    else:
        catalog = modules.load(project)
        observed = catalog['modules'][0]['observations'][-1]
        field, value = {
            'absent': ('availability', 'absent'),
            'unobserved': ('availability', 'unobserved'),
            'baseline-name': ('baseline', 'other'),
            'baseline-hash': ('baseline_sha256', 'b'*64),
        }[invalid]
        observed[field] = value
        write(project.root/CATALOG, catalog)
        message = ('observe the target baseline before init' if invalid.startswith('baseline-')
                   else 'new DUT top must belong to the observed module variants')
    before = tree_state(project.root)
    if via_cli:
        assert main(init_arguments(project, 'three', top, module_id)) == 2
        assert message in capsys.readouterr().err
    else:
        with pytest.raises(UcvError, match=message):
            initialize(project, 'demo', 'frontend', 'three', top, top+'Dut', module_id)
    assert tree_state(project.root) == before
    root = project.suite('demo').path
    assert not (root/'testbenches/three').exists()
    assert not (root/'docs/spec/design/three.md').exists()
    assert not (root/'docs/spec/verification/three.md').exists()


def test_init_honors_persisted_adoption_with_an_older_project_object(project, adoption):
    older_project = Project(project.root)
    modules.adopt(project, adoption, CATALOG)
    before = tree_state(project.root)
    # Reloading the catalog or rejecting a stale Project are both valid;
    # creating an identity-less DUT under the persisted catalog is not.
    with pytest.raises(UcvError):
        initialize(older_project, 'demo', 'frontend', 'three', 'Three', 'ThreeDut')
    assert tree_state(project.root) == before


@pytest.mark.parametrize('existing', ['dut', 'testbench', 'design-spec', 'verification-spec'])
def test_init_protects_registered_and_unregistered_user_files(project, adoption, existing):
    modules.adopt(project, adoption, CATALOG)
    root = project.suite('demo').path
    dut, top = ('one', 'One') if existing == 'dut' else ('three', 'Three')
    if existing != 'dut':
        relative = {'testbench': 'testbenches/three/env.py',
                    'design-spec': 'docs/spec/design/three.md',
                    'verification-spec': 'docs/spec/verification/three.md'}[existing]
        path = root/relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'Unregistered owner work must survive.\r\n\x00')
    before = tree_state(project.root)
    with pytest.raises(UcvError, match='already exists' if existing == 'dut' else 'overwrite'):
        initialize(project, 'demo', 'frontend', dut, top, top+'Dut', FAMILY)
    assert tree_state(project.root) == before


def test_cli_adopt_init_list_and_info_preserve_persistent_names(project, adoption, capsys):
    snapshot = project.root/'adoption.json'
    write(snapshot, adoption)
    prefix = ['--root', str(project.root)]
    assert main([*prefix, 'modules', 'adopt', str(snapshot), '--catalog', CATALOG, '--json']) == 0
    adopted = json.loads(capsys.readouterr().out)
    assert adopted['status'] == 'ADOPTED' and adopted['duts'] == 2
    assert main(init_arguments(project, 'three', 'Three', FAMILY)) == 0
    assert capsys.readouterr().out.strip() == str(project.suite('demo').path)
    reloaded = Project(project.root)
    before = tree_state(project.root)

    assert main([*prefix, 'modules', 'list', '--json']) == 0
    assert json.loads(capsys.readouterr().out) == adoption['catalog']
    assert main([*prefix, 'modules', 'list']) == 0
    tree = capsys.readouterr().out
    assert f'{FAMILY_NAME} [{FAMILY}]' in tree
    assert 'demo/one' in tree and 'demo/three' in tree

    value = info(reloaded, reloaded.suite('demo'), ['three'])
    row = value['duts'][0]
    assert row['module_id'] == FAMILY and row['module_name'] == FAMILY_NAME
    assert row['testbench'] == 'three'
    assert main([*prefix, 'info', 'demo', '--dut', 'three', '--json']) == 0
    assert json.loads(capsys.readouterr().out) == [value]
    assert main([*prefix, 'info', 'demo', '--dut', 'three']) == 0
    rendered = capsys.readouterr().out
    assert rendered.strip() == markdown(value).strip()
    assert FAMILY in rendered and FAMILY_NAME in rendered
    for command in (['modules', 'check'], ['check', 'demo']):
        assert main([*prefix, *command, '--json']) == 0
        result = json.loads(capsys.readouterr().out)
        assert result['status'] == 'PASS' and result['errors'] == []
    assert tree_state(project.root) == before


@pytest.mark.parametrize('invalid', ['unknown-id', 'missing-id', 'top'])
def test_check_reports_bad_persisted_identities_and_tops(project, adoption, invalid, capsys):
    modules.adopt(project, adoption, CATALOG)
    suite = project.suite('demo')
    assert modules.check(project)['errors'] == []
    assert check(project, [suite])['errors'] == []
    if invalid == 'top':
        recipe = read(suite.path/'ucv.json')
        recipe['duts']['one']['top'] = 'Unrelated'
        write(suite.path/'ucv.json', recipe)
        message = 'demo/one: top is outside the observed module variants'
    else:
        meta = metadata(suite)
        if invalid == 'unknown-id':
            meta['duts']['one']['module_id'] = 'unknown.module'
        else:
            del meta['duts']['one']['module_id']
        write(suite.path/'workspace.json', meta)
        message = 'demo/one: missing/unknown module_id'
    before = tree_state(project.root)
    for result in (modules.check(project), check(project, [project.suite('demo')])):
        assert result['status'] == 'FAIL'
        assert message in result['errors']
    for command in (['modules', 'check'], ['check', 'demo']):
        assert main(['--root', str(project.root), *command, '--json']) == 1
        result = json.loads(capsys.readouterr().out)
        assert result['status'] == 'FAIL' and message in result['errors']
    assert tree_state(project.root) == before


def test_module_reference_split_requires_all_successors_and_keeps_original_catalog(project, adoption):
    old = 'docs/old-family.md'
    adoption['catalog']['modules'][0]['references'].append(old)
    (project.root/old).parent.mkdir(exist_ok=True)
    (project.root/old).write_text('# Former family entry\n')
    modules.adopt(project, adoption, CATALOG)
    original = (project.root/CATALOG).read_bytes()
    (project.root/old).unlink()
    for name in ('one', 'two'):
        (project.root/f'docs/{name}.md').write_text('# Independent owner\n')
    write(project.root/'docs/path-migrations.json', {'schema': 2, 'paths': {
        old: ['docs/one.md', 'docs/two.md'],
    }})
    result = modules.check(project)
    assert result['errors'] == []
    assert any('historical reference relocated' in notice for notice in result['notices'])
    (project.root/'docs/two.md').unlink()
    assert any('missing reference: '+old in error for error in modules.check(project)['errors'])
    assert (project.root/CATALOG).read_bytes() == original
