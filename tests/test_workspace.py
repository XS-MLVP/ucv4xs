"""Boundary checks for release imports and small, independent workspaces. MPL-2.0."""
from pathlib import Path
import io
import json
import os
import subprocess
import sys
import tarfile

import pytest

from ucv.common import UcvError, digest, file_hash, read, write
from ucv.config import Project
from ucv.releases import fetch_release, release_spec, unpack, validate_parameters
from ucv.workspace import initialize


def make_project(root):
    write(root/'ucv.json',{'baseline':'test','suites':{'demo':'suites/frontend/demo'},
                         'profiles':{'public':['demo']}})
    write(root/'dependencies/versions.json',{})
    write(root/'baselines/test.json',{'name':'test','repository':'https://example.test/repo.git',
          'commit':'a'*40,'visibility':'public','recursive_submodules':[], 'patches':[],
          'design':{'top':'top.TopMain','config':'DefaultConfig','num_cores':1,'chisel_args':[]},
          'tools':{'mill':'1','chisel':'2','firtool':'3','java':'17'},'firtool_options':[]})
    write(root/'suites/frontend/demo/ucv.json',{'suite':'demo','generation':'soc','pytest_root':'.','tests':['modules'],'duts':{
          'one':{'top':'One','export_name':'OneDut'},'two':{'top':'Two','export_name':'TwoDut'}}})
    project=Project(root)
    suite=project.suite('demo')
    meta={'schema':1,'fixtures':'conftest.py','duts':{}}
    for name in ('__init__.py','conftest.py','modules/__init__.py'):
        p=suite.path/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('')
    (suite.path/'pytest.ini').write_text('[pytest]\ntestpaths = modules\n')
    for key in ('one','two'):
        for name in ('__init__.py','env.py','tests/__init__.py'):
            p=suite.path/'modules'/key/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('')
        for name in ('docs/README.md','docs/spec/design/README.md','docs/spec/verification/README.md','docs/bugs/README.md'):
            p=suite.path/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('# Draft\n')
        meta['duts'][key]={'module':key,'environment':f'modules/{key}/env.py','tests':[f'modules/{key}/tests'],
                         'design_spec':'docs/spec/design/README.md','verification_spec':'docs/spec/verification/README.md'}
    write(suite.path/'workspace.json',meta)
    from ucv.layout import refresh_readmes
    from ucv.documents import refresh_index
    refresh_readmes(project,suite,meta,True)
    refresh_index(project,suite,True)
    return project


def make_release(project):
    baseline=project.baseline('test')
    parameters={'source':{'repository':baseline['repository'],'commit':baseline['commit'],
                         'patches':[],'recursive_submodules':0},
                'design':baseline['design'],'tools':baseline['tools'],
                'generation':{**baseline['design'],'target':'systemverilog','split_verilog':True,
                              'firtool_options':[]}}
    package=project.root/'payload'
    write(package/'BUILD-PARAMETERS.json',parameters)
    (package/'rtl').mkdir()
    (package/'rtl/One.sv').write_text('module One(input clock);\nendmodule\n')
    (package/'rtl/filelist.f').write_text('./One.sv\n')
    sums=''.join(f'{file_hash(p)}  {p.relative_to(package)}\n' for p in sorted(package.rglob('*')) if p.is_file())
    (package/'SHA256SUMS').write_text(sums)
    archive=project.root/'payload.tar.gz'
    with tarfile.open(archive,'w:gz') as stream:stream.add(package,arcname='payload')
    entry={'baseline_sha256':digest(baseline),'url':'https://example.test/payload.tar.gz',
           'sha256':file_hash(archive),'package':'payload'}
    write(project.root/'baselines/rtl-releases.json',{'schema':1,'releases':{'test':entry}})
    return archive,entry,parameters


def test_prepare_release_without_tools_preserves_bytes_and_rejects_corruption(tmp_path,monkeypatch):
    from ucv.cli import main
    import ucv.sources as sources
    project=make_project(tmp_path)
    archive,entry,_=make_release(project)
    monkeypatch.setattr(sources,'generate',lambda *args:pytest.fail('release must not start JVM'))
    args=['--root',str(tmp_path),'prepare','demo','--dut','one','--rtl-source','release','--archive',str(archive)]
    assert main(args)==0
    base=tmp_path/'.cache/duts'/project.cache_key(project.suite('demo'),'one')
    assert (base/'rtl/One.sv').read_bytes()==(tmp_path/'payload/rtl/One.sv').read_bytes()
    assert read(base/'rtl/source.json')['origin']['kind']=='release'
    assert not (tmp_path/'.tools').exists() and not (tmp_path/'.cache/generated').exists()
    rtl=fetch_release(project,project.baseline('test'),archive)
    (rtl/'One.sv').write_text('changed')
    with pytest.raises(UcvError,match='cache is corrupt'):fetch_release(project,project.baseline('test'))
    archive.write_bytes(b'invalid')
    with pytest.raises(UcvError,match='SHA-256 mismatch'):fetch_release(project,project.baseline('test'),archive)
    changed={**project.baseline('test'),'patches':[{'path':'x','sha256':'0'*64}]}
    with pytest.raises(UcvError,match='complete baseline'):release_spec(project,changed)
    (tmp_path/'baselines/rtl-releases.json').unlink()
    with pytest.raises(UcvError,match='generate explicitly'):sources.obtain_rtl(project,project.suite('demo'))


def test_release_rejects_escaping_member_and_wrong_generation_parameters(tmp_path):
    project=make_project(tmp_path)
    archive,entry,parameters=make_release(project)
    with tarfile.open(archive,'w:gz') as stream:
        member=tarfile.TarInfo('payload/../../outside')
        member.size=1
        stream.addfile(member,io.BytesIO(b'x'))
    with pytest.raises(UcvError,match='Unsafe'):unpack(archive,tmp_path/'extract',entry,project.baseline('test'))
    parameters['generation']['firtool_options']=['-O=debug']
    with pytest.raises(UcvError,match='disagrees'):validate_parameters(parameters,project.baseline('test'))
    assert not (tmp_path/'outside').exists()


def test_init_preserves_existing_work_and_emits_explicit_unimplemented_test(tmp_path):
    project=make_project(tmp_path)
    initialize(project,'demo','frontend','three','Three','ThreeDut')
    assert (project.suite('demo').path/'modules/three/env.py').is_file()
    assert read(project.suite('demo').path/'workspace.json')['duts']['three']['module']=='three'
    path=Path(initialize(project,'fresh','frontend','leaf','Leaf','LeafDut'))
    assert Project(tmp_path).suite('fresh').recipe['duts']['leaf']['top']=='Leaf'
    assert 'fresh' not in read(tmp_path/'ucv.json')['profiles']['public']
    test=path/'testbenches/leaf/tests/test_leaf_smoke.py'
    assert 'pytest.fail(' in test.read_text()
    from ucv.workspace import check
    assert (path/'docs/spec/design/leaf.md').is_file()
    assert (path/'docs/spec/verification/leaf.md').is_file()
    assert (path/'docs/bugs/open').is_dir() and (path/'docs/bugs/closed').is_dir()
    assert check(Project(tmp_path),[Project(tmp_path).suite('fresh')])['errors']==[]
    # Reusing the same Project also supports adding another DUT to the new suite.
    initialize(project,'fresh','frontend','second','Second','SecondDut')
    assert check(project,[project.suite('fresh')])['errors']==[]
    from ucv.layout import refresh_readmes, problems
    suite=project.suite('fresh')
    meta=read(path/'workspace.json')
    assert meta['schema']==2 and meta['duts']['leaf']['testbench']=='leaf'
    assert suite.recipe['tests']==['testbenches']
    readme=path/'testbenches/leaf/README.md'
    readme.write_text(readme.read_text()+'\nOwner notes.\n')
    refresh_readmes(project,suite,meta,write=True)
    assert readme.read_text().endswith('\nOwner notes.\n')
    (path/'pytest.ini').write_text('[pytest]\ntestpaths = tests\n')
    (path/'testbenches/leaf/env').mkdir()
    errors=problems(suite,meta)
    assert 'pytest.ini testpaths must be testbenches' in errors
    assert 'leaf: choose env.py or env/, not both' in errors
    (path/'testbenches/leaf/env').rmdir()
    (path/'pytest.ini').write_text('[pytest]\ntestpaths = testbenches\n')
    from ucv.layout import relocated_name, relocated
    write(path/'docs/path-migrations.json',{'schema':1,'paths':{
        'tests/old.py':'modules/leaf/tests/test_leaf_smoke.py',
        'tests/mixed.py::test_second':'modules/second/tests/test_second_smoke.py::test_smoke',
        'modules':'testbenches'}})
    assert relocated(path,'tests/old.py')==path/'testbenches/leaf/tests/test_leaf_smoke.py'
    assert relocated_name(path,'tests/mixed.py::test_second[x]')=='testbenches/second/tests/test_second_smoke.py::test_smoke[x]'
    migration=read(path/'docs/path-migrations.json')
    for destination in ('tests/old.py','modules/leaf/tests/test_leaf_smoke.py/nested'):
        write(path/'docs/path-migrations.json',{'schema':1,'paths':{
            'tests/old.py':'modules/leaf/tests/test_leaf_smoke.py',
            'modules/leaf/tests/test_leaf_smoke.py':destination}})
        with pytest.raises(UcvError,match='cycle'):relocated_name(path,'tests/old.py')
    write(path/'docs/path-migrations.json',migration)
    nav=read(path/'docs/navigation.json')
    nav['relocations']={'spec/design/leaf.md':'docs/spec/design/leaf.md'}
    write(path/'docs/navigation.json',nav)
    assert check(Project(tmp_path),[Project(tmp_path).suite('fresh')])['errors']==[]
    nav['relocations']['spec/design/leaf.md']='docs/spec/design/missing.md'
    write(path/'docs/navigation.json',nav)
    assert any('missing relocated document' in error for error in
               check(Project(tmp_path),[Project(tmp_path).suite('fresh')])['errors'])
    nav['relocations']['spec/design/leaf.md']='docs/spec/design/leaf.md'
    write(path/'docs/navigation.json',nav)
    before={str(p):file_hash(p) for p in path.rglob('*') if p.is_file()}
    with pytest.raises(UcvError,match='already exists'):
        initialize(Project(tmp_path),'fresh','frontend','leaf','Leaf','LeafDut')
    assert before=={str(p):file_hash(p) for p in path.rglob('*') if p.is_file()}
    (path/'testbenches/other').mkdir()
    (path/'testbenches/other/env.py').write_text('user work')
    with pytest.raises(UcvError,match='overwrite'):
        initialize(Project(tmp_path),'fresh','frontend','other','Other','OtherDut')
    assert (path/'testbenches/other/env.py').read_text()=='user work'
    assert 'other' not in read(path/'ucv.json')['duts']
    # A valid testbench must not let a second unowned test tree bypass the rule.
    (path/'tests').mkdir()
    (path/'tests/test_unowned.py').write_text('def test_unowned(): pass\n')
    result=check(Project(tmp_path),[Project(tmp_path).suite('fresh')])
    assert any('unexpected directory at suite root: tests' in e for e in result['errors'])


def test_layout_rejects_physical_extras_even_without_python_sources(tmp_path):
    from ucv.workspace import check
    project=make_project(tmp_path)
    suite=project.suite('demo')
    root=suite.path
    # Standard local artifacts and metadata remain legal in an initialized suite.
    for name in ('runtime','tools','dependencies','manifest','dut','rtl','results',
                 '__pycache__','.pytest_cache','docs/guides','docs/bugs/evidence'):
        (root/name).mkdir(parents=True,exist_ok=True)
    write(root/'dependencies/versions.json',{})
    write(root/'manifest/baseline.json',{})
    (root/'XiangShan').symlink_to(tmp_path/'source-cache',target_is_directory=True)
    (root/'dut/one').symlink_to(tmp_path/'native-cache',target_is_directory=True)
    assert check(project,[suite])['errors']==[]
    # Empty, cache-only, document-only and hidden directories all used to escape.
    for name in ('drivers','monitors','notes','.scratch'):(root/name).mkdir()
    (root/'monitors/__pycache__').mkdir()
    (root/'monitors/__pycache__/old.pyc').write_bytes(b'old cache')
    (root/'notes/README.md').write_text('owner notes')
    (root/'old-link').symlink_to('modules',target_is_directory=True)
    (root/'missing-link').symlink_to('absent',target_is_directory=True)
    (root/'memory-direct.fst').write_bytes(b'waveform')
    (root/'modules/unregistered').mkdir()
    (root/'modules/one/agent').mkdir()
    (root/'modules/one/checker.py').mkdir()  # A Python filename is not a directory role.
    (root/'modules/one/model').symlink_to('../two',target_is_directory=True)
    (root/'docs/history').mkdir()
    (root/'manifest/hidden_model').mkdir(parents=True)
    failures=check(project,[suite])['errors']
    for suffix in ('suite root: drivers','suite root: monitors','suite root: notes',
                   'suite root: .scratch','suite root: old-link','suite root: missing-link',
                   'suite root: memory-direct.fst','modules: unregistered','module one: agent',
                   'module one: checker.py','module one: model','docs: history','manifest: hidden_model'):
        assert any(error.endswith(suffix) for error in failures), (suffix,failures)
    # Inspecting a bad layout must preserve both user data and link targets.
    assert (root/'notes/README.md').read_text()=='owner notes'
    assert (root/'modules/two/env.py').is_file()
    # Adding a new DUT must reject an invalid suite before changing its contents.
    before=(root/'ucv.json').read_bytes(),(root/'workspace.json').read_bytes()
    with pytest.raises(UcvError,match='Existing suite violates module layout'):
        initialize(project,'demo','frontend','three','Three','ThreeDut')
    assert before==((root/'ucv.json').read_bytes(),(root/'workspace.json').read_bytes())
    assert not (root/'modules/three').exists()


def test_schema2_shared_contract_imports_navigation_and_actual_selection(tmp_path,monkeypatch):
    import ucv.validation as validation
    from ucv.layout import collection_plugins, problems, refresh_readmes
    from ucv.run import run
    from ucv.workspace import check, info, metadata, test_roots
    project=make_project(tmp_path)
    legacy=project.suite('demo')
    assert info(project,legacy)['duts'][0]['module']=='one'
    (legacy.path/'testbenches').mkdir()
    assert 'unexpected directory at suite root: testbenches' in problems(legacy,metadata(legacy))
    (legacy.path/'testbenches').rmdir()
    root=Path(initialize(project,'fresh','frontend','leaf','Leaf','LeafDut'))
    suite=project.suite('fresh')
    meta=metadata(suite)
    assert test_roots(suite,['leaf'])==[root/'testbenches/leaf/tests']
    shared=root/'testbenches/shared'
    (shared/'env').mkdir(parents=True)
    (shared/'__init__.py').write_text('')
    (shared/'env/__init__.py').write_text('')
    plugin=shared/'env/plugin.py'
    plugin.write_text('def pytest_addoption(parser):\n    parser.addoption("--shared-probe", action="store_true")\n')
    refresh_readmes(project,suite,meta,True)
    assert check(project,[suite])['errors']==[]  # Shared tests are optional.
    (shared/'tests').mkdir()
    assert 'shared: missing tests/__init__.py' in problems(suite,meta)
    (shared/'tests/__init__.py').write_text('')
    (shared/'tests/test_shared.py').write_text(
        'from .. import env\nfrom ...leaf.env import Environment\ndef test_shared(): assert Environment\n')
    (root/'conftest.py').write_text('pytest_plugins=("ucv.pytest_selftest", "suites.frontend.fresh.testbenches.shared.env.plugin")\n')
    assert collection_plugins(suite)==['ucv.pytest_selftest','suites.frontend.fresh.testbenches.shared.env.plugin']
    refresh_readmes(project,suite,meta,True)
    row=info(project,suite)['duts'][0]
    assert row['testbench']=='leaf' and 'module' not in row
    assert row['resources']['shared'][0]['path']==str(shared/'README.md')
    checked=check(project,[suite])
    assert checked['errors']==[]
    assert 'testbenches/shared/README.md' in checked['documents'][1]['current']
    assert test_roots(suite,['leaf'])==[root/'testbenches/leaf/tests',shared/'tests']
    readme=(shared/'README.md').read_text()
    (shared/'README.md').write_text(readme+'\n[bad link](missing.md)\n')
    assert any('shared/README.md: missing local link' in e for e in check(project,[suite])['errors'])
    (shared/'README.md').write_text(readme)

    # Exercise the real launcher: default DUT selection includes shared; an
    # explicit nodeid and -m still replace/filter that default as pytest intends.
    monkeypatch.setattr(project,'runtime_python',lambda:Path(sys.executable))
    monkeypatch.setattr(validation,'installed_tools',lambda *args:{})
    monkeypatch.setenv('PYTHONPATH',str(Path(__file__).resolve().parents[1]/'src'))
    monkeypatch.setenv('PYTEST_DISABLE_PLUGIN_AUTOLOAD','1')
    leaf='testbenches/leaf/tests/test_leaf_smoke.py::test_smoke'
    shared_case='testbenches/shared/tests/test_shared.py::test_shared'
    for selectors,expected in (([],[leaf,shared_case]),([leaf],[leaf]),(['-m','selftest'],[shared_case])):
        output,result=run(project,[suite],workers=1,duts=['leaf'],collect_only=True,
                          pytest_args=['--shared-probe',*selectors])
        assert result['status']=='PASS'
        assert read(output/'cases/fresh/cases.json')['collected']==expected

    # Shared implementation cannot import DUTs, including parent-package and
    # ordinary relative forms; test-only imports above are deliberately legal.
    implementation=shared/'env/imports.py'
    implementation.write_text('from . import plugin\nfrom .. import env\nfrom ...shared import env as shared_env\n')
    assert problems(suite,meta)==[]
    for statement in ('import suites.frontend.fresh.testbenches.leaf.env',
                      'from suites.frontend.fresh.testbenches import leaf',
                      'from ...leaf.env import Environment', 'from ... import leaf',
                      'from ....testbenches.leaf import env', 'import testbenches.leaf.env',
                      'from ....tools import summarize', 'from suites.frontend.fresh import tools',
                      'import tools.summary'):
        implementation.write_text(statement+'\n')
        assert any('shared implementation imports' in e for e in problems(suite,meta)),statement
    implementation.unlink()
    entry=meta['duts']['leaf']
    for invalid in ({**entry,'testbench':'shared'},{**entry,'module':'leaf'},
                    {k:v for k,v in entry.items() if k!='testbench'}):
        write(root/'workspace.json',{**meta,'duts':{'leaf':invalid}})
        with pytest.raises(UcvError):metadata(suite)
    write(root/'workspace.json',meta)
    suite.recipe['duts']['shared']=suite.recipe['duts']['leaf']
    write(root/'workspace.json',{**meta,'duts':{**meta['duts'],'shared':entry}})
    with pytest.raises(UcvError,match='shared is reserved'):metadata(suite)
    del suite.recipe['duts']['shared']
    write(root/'workspace.json',meta)
    # Parameterized DUTs can explicitly share one testbench; shared stays outside
    # the recipe's DUT registry and is appended to the selected roots just once.
    suite.recipe['duts']['variant']=suite.recipe['duts']['leaf']
    write(root/'workspace.json',{**meta,'duts':{**meta['duts'],'variant':entry}})
    assert test_roots(suite,['leaf','variant'])==[root/'testbenches/leaf/tests',shared/'tests']
    del suite.recipe['duts']['variant']
    write(root/'workspace.json',meta)
    for name in ('modules','runtime','testbenches/.hidden','testbenches/shared/extra'):
        (root/name).mkdir()
    (shared/'env.py').write_text('')
    (shared/'model').symlink_to('absent',target_is_directory=True)
    (shared/'tests/conftest.py').write_text('')
    (shared/'tests/pytest.ini').write_text('[pytest]\n')
    failures=problems(suite,meta)
    for message in ('suite root: modules','suite root: runtime','testbenches: .hidden',
                    'testbench shared: extra','testbench shared: model',
                    'shared: choose env.py or env/, not both',
                    'fixture registration belongs at suite root', 'pytest configuration belongs at suite root'):
        assert any(message in e for e in failures),(message,failures)
    before=(root/'ucv.json').read_bytes(),(root/'workspace.json').read_bytes()
    with pytest.raises(UcvError,match='Existing suite violates testbench layout'):
        initialize(project,'fresh','frontend','other','Other','OtherDut')
    assert before==((root/'ucv.json').read_bytes(),(root/'workspace.json').read_bytes())


def test_source_navigation_uses_submodule_revisions_and_distinguishes_missing_checkout(tmp_path):
    from ucv.sources import source_key
    from ucv.workspace import check, info
    project=make_project(tmp_path)
    baseline=read(tmp_path/'baselines/test.json')
    baseline['recursive_submodules']=[
        {'path':'utility','repository':'https://example.test/utility.git','commit':'b'*40},
        {'path':'utility/vendor/math','repository':'https://example.test/math.git','commit':'c'*40}]
    write(tmp_path/'baselines/test.json',baseline)
    suite=project.suite('demo')
    paths=['src/One.scala','utility/src/Leaf.scala','utility/vendor/math/src/Adder.scala']
    meta=read(suite.path/'workspace.json')
    meta['duts']['one']['chisel']=paths
    write(suite.path/'workspace.json',meta)
    resources=info(project,suite,['one'])['duts'][0]['resources']['chisel']
    assert [r['url'] for r in resources]==[
        'https://example.test/repo/blob/'+'a'*40+'/src/One.scala',
        'https://example.test/utility/blob/'+'b'*40+'/src/Leaf.scala',
        'https://example.test/math/blob/'+'c'*40+'/src/Adder.scala']
    absent=check(project,[suite])
    assert absent['errors']==[]
    assert any('two: chisel 未登记' in note for note in absent['notices'])
    assert any('source checkout unavailable' in note for note in absent['notices'])
    source=tmp_path/'.cache/sources'/source_key(baseline)
    assert not source.exists()  # Navigation checks must remain read-only/offline.
    for name in paths:
        path=source/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text('// local source fixture\n')
    present=check(project,[suite])
    assert present['errors']==[]
    assert not any('source checkout unavailable' in note for note in present['notices'])
    (source/paths[1]).unlink()
    missing=check(project,[suite])
    assert missing['status']=='FAIL'
    assert len(missing['errors'])==1 and 'missing chisel in source checkout' in missing['errors'][0]


def test_single_dut_run_needs_only_its_build_and_rejects_cross_dut_collection(tmp_path,monkeypatch):
    import ucv.validation as validation
    from ucv.run import run
    project=make_project(tmp_path)
    suite=project.suite('demo')
    (suite.path/'pytest.ini').write_text('[pytest]\n')
    for name in ('one','two'):
        directory=suite.path/'modules'/name/'tests'
        directory.mkdir(parents=True,exist_ok=True)
        (directory/f'test_{name}.py').write_text('def test_value(): assert True\n')
    # Reuse this test's installed runner; relocating a Python symlink is not a venv.
    monkeypatch.setattr(project,'runtime_python',lambda:Path(sys.executable))
    source=str(Path(__file__).resolve().parents[1]/'src')
    monkeypatch.setenv('PYTHONPATH',source)
    monkeypatch.setenv('PYTEST_DISABLE_PLUGIN_AUTOLOAD','1')
    monkeypatch.setattr(validation,'installed_tools',lambda *args:{})
    base=tmp_path/'.cache/duts'/project.cache_key(suite,'one')
    (base/'dut').mkdir(parents=True)
    (base/'rtl').mkdir()
    (base/'dut/__init__.py').write_text('# synthetic build fixture\n')
    (base/'rtl/One.sv').write_text('module One(); endmodule\n')
    write(base/'build.json',{'baseline':suite.baseline,'smoke':'PASS',
          'outputs':{'__init__.py':file_hash(base/'dut/__init__.py')},
          'rtl':{'One.sv':file_hash(base/'rtl/One.sv')}})
    (suite.path/'dut').mkdir()
    (suite.path/'dut/one').symlink_to(base/'dut')
    output,result=run(project,[suite],workers=1,duts=['one'])
    assert result['status']=='PASS'
    assert read(output/'demo-builds.json').keys()=={'one'}
    cases=read(output/'cases/demo/cases.json')
    assert cases['collected']==['modules/one/tests/test_one.py::test_value']
    env={**os.environ,'UCV_TEST_ROOTS':json.dumps([str(suite.path/'modules/one/tests')])}
    wrong=subprocess.run([sys.executable,'-m','pytest','--collect-only','-q','-p','ucv.pytest_plugin',
                          'modules/two/tests'],cwd=suite.path,env=env,capture_output=True,text=True)
    assert wrong.returncode!=0 and 'outside the selected DUT' in wrong.stderr+wrong.stdout


def test_bug_index_preserves_prose_and_rejects_duplicate_or_unproven_closure(tmp_path):
    from ucv.documents import issues, refresh_index
    project=make_project(tmp_path)
    suite=project.suite('demo')
    root=suite.path/'docs/bugs'
    (root/'open').mkdir(parents=True,exist_ok=True)
    (root/'closed').mkdir()
    readme=root/'README.md'
    readme.write_text('# Owner notes\n\nKeep this hand-written explanation.\n')
    data={'id':'DEMO-001','title':'lost request','kind':'investigation'}
    def bug(path,row):path.write_text('```ucv-bug\n'+json.dumps(row)+'\n```\n\nOriginal evidence.\n')
    bug(root/'open/DEMO-001.md',data)
    preview=refresh_index(project,suite)
    assert not preview['index_current'] and 'DEMO-001' not in readme.read_text()
    assert '未登记复验' in preview['markdown']
    refresh_index(project,suite,write=True)
    assert 'Keep this hand-written explanation.' in readme.read_text()
    assert not refresh_index(project,suite,write=True)['updated']
    bug(root/'closed/duplicate.md',data)
    with pytest.raises(UcvError,match='duplicate bug ID'):issues(suite)
    (root/'closed/duplicate.md').unlink()
    (root/'open/DEMO-001.md').rename(root/'closed/DEMO-001.md')
    with pytest.raises(UcvError,match='resolution'):issues(suite)
    data['resolution']={'reason':'invalid','evidence':['contract at reviewed commit'],'note':'Input excluded by contract.'}
    bug(root/'closed/DEMO-001.md',data)
    assert issues(suite)[0]['state']=='closed'


def test_bug_snapshots_and_consumed_markdown_participate_in_iteration_identity(tmp_path):
    from ucv.documents import compare_issues
    from ucv.run import source_identity, declared
    project=make_project(tmp_path)
    suite=project.suite('demo')
    contract=suite.path/'docs/spec/verification/contract.md'
    contract.parent.mkdir(parents=True,exist_ok=True)
    contract.write_text('original requirement')
    before=source_identity(project,[suite])
    contract.write_text('changed requirement')
    assert before['sha256']!=source_identity(project,[suite])['sha256']
    record=suite.path/'docs/bugs/open/DEMO-001.md'
    record.parent.mkdir(parents=True)
    record.write_text('```ucv-bug\n{"id":"DEMO-001","title":"loss","kind":"rtl"}\n```\n')
    frozen=declared(suite)
    record.write_text(record.read_text()+'Later analysis.\n')
    assert frozen['bugs'][0]['sha256']!=declared(suite)['bugs'][0]['sha256']
    new={**frozen,'bugs':[{**frozen['bugs'][0],'state':'closed'}]}
    assert compare_issues([frozen],[new])['closed']==['demo::DEMO-001']
    assert compare_issues([new],[frozen])['reopened']==['demo::DEMO-001']
    assert compare_issues([{'suite':'demo'}],[frozen])['unavailable_suites']==['demo']
    from ucv.report import report
    for name, snapshot, fingerprint in [('before',frozen,'old'),('after',new,'new')]:
        write(tmp_path/name/'run.json',{'status':'PASS','mixed_baseline':False,'suites':[snapshot],
              'source':{'sha256':fingerprint},'tasks':[],'seed':1,'collect_only':True,
              'selected_duts':{'demo':['one']},'pytest_args':[]})
    report(tmp_path/'before')
    summary=report(tmp_path/'after',tmp_path/'before')
    assert summary['comparison']['bugs']['closed']==['demo::DEMO-001']
    assert summary['comparison']['same_verification_source'] is False
    assert summary['hardware_verdict']=='INCOMPLETE'  # a closed record is not execution credit
