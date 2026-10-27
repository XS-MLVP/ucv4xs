import json
from pathlib import Path
import pytest
from ucv.config import Project
from ucv.common import UcvError, write

@pytest.fixture
def project(tmp_path):
    write(tmp_path/'ucv.json',{'baseline':'a','suites':{'bpu':'suites/frontend/bpu','lsq':'suites/memblock/lsq'},'profiles':{'public':['bpu','lsq']}})
    write(tmp_path/'dependencies/versions.json',{'toffee':{'commit':'1'*40}})
    for name,commit in [('a','1'*40),('b','2'*40),('c','3'*40)]:
        write(tmp_path/'baselines'/f'{name}.json',{'name':name,'repository':'https://example.test/source.git','commit':commit,
            'recursive_submodules':[],'design':{'config':'DefaultConfig','num_cores':1,'top':'top.TopMain'},
            'patches':[],'tools':{'mill':'0.12.17','chisel':'7.13.0','firtool':'1.149.0','java':'17'},
            'firtool_options':[],'visibility':'public'})
    for name,path in [('bpu','frontend'),('lsq','memblock')]:
        write(tmp_path/f'suites/{path}/{name}/ucv.json',{'suite':name,'generation':'soc','duts':{'unit':{'top':'Unit','export_name':'UnitDut'}}})
    return Project(tmp_path)

def test_nearest_whole_suite_override_and_origin(project):
    assert project.suite('bpu').inherited_from=='ucv.json'
    write(project.root/'suites/frontend/ucv.json',{'baseline':'b'})
    assert project.suite('bpu').baseline['name']=='b'
    path=project.root/'suites/frontend/bpu/ucv.json'
    data=json.loads(path.read_text());data['baseline']='c';write(path,data)
    suite=project.suite('bpu')
    assert suite.baseline['name']=='c'
    assert suite.inherited_from=='suites/frontend/bpu/ucv.json'
    assert project.suite('lsq').baseline['name']=='a'

def test_mixed_preflight_and_selection_errors(project):
    assert len(project.select(['public'],unified=True))==2
    write(project.root/'suites/frontend/ucv.json',{'baseline':'b'})
    with pytest.raises(UcvError,match='Mixed baselines'):project.select(['public'],unified=True)
    assert len(project.select(['frontend'],unified=True))==1
    with pytest.raises(UcvError,match='Unknown'):project.select(['typo'])

@pytest.mark.parametrize('value',['unknown',None,{'commit':'123'},'../escape'])
def test_bad_reference_never_falls_back(project,value):
    write(project.root/'suites/frontend/ucv.json',{'baseline':value})
    with pytest.raises(UcvError):project.suite('bpu')

def test_incomplete_baseline_and_per_dut_overrides(project):
    path=project.root/'baselines/a.json';data=json.loads(path.read_text());del data['tools']['firtool'];write(path,data)
    with pytest.raises(UcvError,match='incomplete'):project.suite('bpu')
    data['tools']['firtool']='1.149.0';write(path,data)
    path=project.root/'suites/frontend/bpu/ucv.json';data=json.loads(path.read_text());data['duts']['unit']['commit']='f'*40;write(path,data)
    with pytest.raises(UcvError,match='per-DUT'):project.suite('bpu')

def test_cache_separates_baseline_dut_tools_and_options(project):
    suite=project.suite('bpu');original=project.cache_key(suite,'unit')
    assert original!=project.cache_key(suite,'another')
    assert original!=project.cache_key(suite,'unit',{'trace':True})
    assert original!=project.cache_key(project.suite('lsq'),'unit')
    write(project.root/'suites/frontend/ucv.json',{'baseline':'b'})
    assert original!=project.cache_key(project.suite('bpu'),'unit')
    project.tools['toffee']['commit']='f'*40
    assert original!=project.cache_key(suite,'unit')

@pytest.mark.parametrize('field,value', [
    ('design', {'config':'','num_cores':1,'top':'top.TopMain'}),
    ('design', {'config':'DefaultConfig','num_cores':0,'top':'top.TopMain'}),
    ('visibility', 'unknown'), ('commit', '893e1580b'),
    ('firtool_options', '-O=release'), ('recursive_submodules', {}),
])
def test_partial_or_ambiguous_definition_is_rejected(project, field, value):
    path=project.root/'baselines/a.json'
    data=json.loads(path.read_text());data[field]=value;write(path,data)
    with pytest.raises(UcvError):project.suite('bpu')


def test_generation_config_changes_baseline_and_cache_identity(project):
    before=project.suite('bpu')
    path=project.root/'baselines/a.json';data=json.loads(path.read_text())
    data['design']['config']='AnotherConfig';write(path,data)
    after=project.suite('bpu')
    assert before.baseline_key != after.baseline_key
    assert project.cache_key(before,'unit') != project.cache_key(after,'unit')
    assert after.summary()['design_config']=='AnotherConfig'


def test_dut_cannot_override_design_configuration(project):
    path=project.root/'suites/frontend/bpu/ucv.json';data=json.loads(path.read_text())
    data['duts']['unit']['config']='MinimalConfig';write(path,data)
    with pytest.raises(UcvError,match='per-DUT'):project.suite('bpu')


def test_standalone_generation_is_rejected(project):
    path = project.root/'suites/frontend/bpu/ucv.json'
    data = json.loads(path.read_text())
    data['generation'] = 'bpu-standalone'
    write(path, data)
    with pytest.raises(UcvError, match='unsupported generation'):
        project.suite('bpu')


def test_whole_chip_generation_is_shared_and_tracks_baseline(project, monkeypatch):
    from subprocess import CompletedProcess
    from ucv import sources
    from ucv.build import prepare
    from ucv.runtime import soc_rtl

    checkout = project.root/'.cache/test-source'
    checkout.mkdir(parents=True)
    (checkout/'.mill-version').write_text('0.12.17\n')
    (checkout/'build.sc').write_text('chiselVersion = "7.13.0"\n')
    tools = project.root/'.tools/bin'
    tools.mkdir(parents=True)
    for name in ('mill', 'firtool'):
        (tools/name).touch()
    calls = []

    def compiler(command, **kwargs):
        if str(command[0]).endswith('/firtool'):
            return CompletedProcess(command, 0, stdout='firtool-1.149.0')
        calls.append(command)
        assert command[5] == 'top.TopMain'
        assert command[command.index('--config')+1] == 'DefaultConfig'
        output = Path(command[command.index('--target-dir')+1])
        (output/'Unit.sv').write_text('module Unit(input clock); endmodule\n')
        return CompletedProcess(command, 0, stdout='')

    monkeypatch.setattr(sources, 'source', lambda *args: checkout)
    monkeypatch.setattr(sources, 'execute', compiler)
    monkeypatch.setenv('UCV_ROOT', str(project.root))
    # Real closure extraction: two suites share generation but own their DUT caches.
    first = prepare(project, project.suite('bpu'), 'unit')
    second = prepare(project, project.suite('lsq'), 'unit')
    assert first != second
    before = json.loads((first/'rtl/source.json').read_text())
    peer = json.loads((second/'rtl/source.json').read_text())
    assert before['source'] == peer['source'] == str(soc_rtl('a'))
    assert before['files'] == peer['files']
    assert len(calls) == 1
    assert not (checkout/'src').exists()  # No injected Scala entry.
    # A group override generates another whole-chip design; no cross-baseline reuse.
    write(project.root/'suites/frontend/ucv.json', {'baseline':'b'})
    changed = prepare(project, project.suite('bpu'), 'unit')
    assert changed != first
    assert len(calls) == 2
    after = json.loads((changed/'rtl/source.json').read_text())
    assert after['source'] != before['source']
    assert after['source'] == str(soc_rtl('b'))
    # A corrupt shared result must never be accepted as another suite's RTL.
    (Path(before['source'])/'Unit.sv').write_text('corrupt')
    with pytest.raises(UcvError, match='cache is corrupt'):
        sources.generate(project, project.suite('lsq'))
