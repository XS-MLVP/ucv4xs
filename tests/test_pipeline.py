import pytest
from ucv.build import closure, repair_python_keywords
from ucv.common import UcvError, write
from ucv.pytest_plugin import verdict
from ucv.report import report

def test_closure_rejects_unresolved_and_duplicate_modules(tmp_path):
    (tmp_path/'Top.sv').write_text('module Top(input clock);\n Child instance(clock);\nendmodule\n')
    with pytest.raises(UcvError,match='Unresolved'):closure(tmp_path,'Top')
    (tmp_path/'Child.sv').write_text('module Child(input clock);\n// Missing fake(clock);\nendmodule\n')
    assert {p.name for p in closure(tmp_path,'Top')}=={'Top.sv','Child.sv'}
    (tmp_path/'Duplicate.sv').write_text('module Child(); endmodule')
    with pytest.raises(UcvError,match='Ambiguous'):closure(tmp_path,'Top')

def test_binding_keyword_fix_preserves_signal_name(tmp_path):
    p=tmp_path/'__init__.py'
    p.write_text('class DUT:\n    def __init__(self):\n        self.in = 12\n        self.input = 13\n        self.x = self.in\n')
    assert repair_python_keywords(p)['changed']
    ns={};exec(compile(p.read_text(),str(p),'exec'),ns)
    obj=ns['DUT']();assert getattr(obj,'in')==obj.x==12 and obj.input==13
    assert not repair_python_keywords(p)['changed']

def test_real_fail_xfail_and_incomplete_are_distinct():
    def phases(value,xfail=None):
        return {'setup':{'outcome':'passed'},'call':{'outcome':value,'wasxfail':xfail},'teardown':{'outcome':'passed'}}
    assert verdict(phases('failed'))=='FAIL'
    assert verdict(phases('skipped','known bug'))=='XFAIL'
    assert verdict(phases('passed','unexpected'))=='XPASS'
    assert verdict({'setup':{'outcome':'passed'}})=='INCOMPLETE'
    assert verdict({**phases('passed'),'teardown':{'outcome':'failed'}})=='ERROR'

def test_report_keeps_hardware_fail_separate_from_migration(tmp_path):
    write(tmp_path/'run.json',{'status':'FAIL','suites':[],'mixed_baseline':False,
        'tasks':[{'suite':'lsu','scope':'suite','cases':'cases.json'}]})
    write(tmp_path/'cases.json',{'cases':{'tests/test_bug.py::test_bug':{'verdict':'FAIL'}},
        'collected':['tests/test_bug.py::test_bug'],'collect_only':False})
    value=report(tmp_path)
    assert value['hardware_verdict']=='FAIL'
    assert value['counts']=={'FAIL':1}
    assert value['migration_acceptance']=='NOT_CERTIFIED'

def test_residual_register_blocks_a_green_verdict(tmp_path):
    """Unproven scope is not a status, so it must be able to stop a PASS."""
    write(tmp_path/'run.json',{'status':'PASS','mixed_baseline':False,'suites':[
        {'suite':'ifu','baseline':'b','inherited_from':'ucv.json','residuals':[
            {'id':'R-13','category':'defect','blocking':True,'acceptance':'open',
             'owner':'FrontendTrigger','next_action':'compare all 64 bits'},
            {'id':'R-01','category':'structural','blocking':False,'acceptance':'accepted-limited',
             'owner':'verification','next_action':'n/a'}]}],
        'tasks':[{'suite':'ifu','scope':'suite','cases':'cases.json'}]})
    write(tmp_path/'cases.json',{'cases':{'tests/test_a.py::test_a':{'verdict':'PASS'}},
        'collected':['tests/test_a.py::test_a'],'collect_only':False})
    value=report(tmp_path)
    assert value['counts']=={'PASS':1}
    assert value['hardware_verdict']=='INCOMPLETE'
    assert any('R-13' in g for g in value['gaps'])
    assert value['residual_summary']['blocking_open']==1
    text=(tmp_path/'summary.md').read_text()
    assert 'Residual register' in text and 'R-13' in text


def test_accepted_residuals_do_not_change_a_pass(tmp_path):
    write(tmp_path/'run.json',{'status':'PASS','mixed_baseline':False,'suites':[
        {'suite':'ifu','baseline':'b','inherited_from':'ucv.json','residuals':[
            {'id':'R-01','category':'structural','blocking':False,'acceptance':'accepted-limited',
             'owner':'verification','next_action':'n/a'}]}],
        'tasks':[{'suite':'ifu','scope':'suite','cases':'cases.json'}]})
    write(tmp_path/'cases.json',{'cases':{'tests/test_a.py::test_a':{'verdict':'PASS'}},
        'collected':['tests/test_a.py::test_a'],'collect_only':False})
    value=report(tmp_path)
    assert value['hardware_verdict']=='PASS'
    assert value['residual_summary']['total']==1
    assert value['gaps']==[]

def test_declared_incomplete_is_neither_pass_nor_failure(tmp_path):
    """A test that runs and covers part of its point must not look green."""
    write(tmp_path/'run.json',{'status':'PASS','mixed_baseline':False,'suites':[
        {'suite':'ifu','baseline':'b','inherited_from':'ucv.json'}],
        'tasks':[{'suite':'ifu','scope':'suite','cases':'cases.json'}]})
    write(tmp_path/'cases.json',{'cases':{
            'tests/test_a.py::test_full':{'verdict':'PASS'},
            'tests/test_b.py::test_partial':{'verdict':'INCOMPLETE',
                'declared_incomplete':{'reason':'one carry position only','residual':'R-09'}}},
        'collected':['tests/test_a.py::test_full','tests/test_b.py::test_partial'],
        'collect_only':False})
    value=report(tmp_path)
    assert value['counts']=={'PASS':1,'INCOMPLETE':1}
    assert value['hardware_verdict']=='INCOMPLETE'
    assert value['incomplete_summary']=={'declared':1,'undeclared':0}
    row=value['declared_incomplete'][0]
    assert row['residual']=='R-09' and row['nodeid']=='tests/test_b.py::test_partial'
    text=(tmp_path/'summary.md').read_text()
    assert 'Declared incomplete' in text and 'R-09' in text


def test_failure_outranks_uncertain(tmp_path):
    """UNCERTAIN must never soften a real FAIL."""
    write(tmp_path/'run.json',{'status':'FAIL','mixed_baseline':False,'suites':[
        {'suite':'ifu','baseline':'b','inherited_from':'ucv.json',
         'residuals':[{'id':'R-13','category':'defect','blocking':False,
                       'acceptance':'open','owner':'x','next_action':'y'}]}],
        'tasks':[{'suite':'ifu','scope':'suite','cases':'cases.json'}]})
    write(tmp_path/'cases.json',{'cases':{
            'tests/test_a.py::test_fail':{'verdict':'FAIL'},
            'tests/test_b.py::test_partial':{'verdict':'UNCERTAIN',
                'uncertain':{'reason':'partial','reference':'R-09'}}},
        'collected':['tests/test_a.py::test_fail','tests/test_b.py::test_partial'],
        'collect_only':False})
    assert report(tmp_path)['hardware_verdict']=='FAIL'


def test_old_incomplete_marker_requires_explicit_migration():
    from ucv.pytest_plugin import pytest_collection_modifyitems as collect

    class Item:
        nodeid='tests/test_x.py::test_x'
        user_properties=[]
        def __init__(self,marker):self._marker=marker
        def get_closest_marker(self,name):return self._marker if name=='incomplete' else None
    class Marker:
        def __init__(self,**kwargs):self.kwargs=kwargs
    with pytest.raises(pytest.UsageError,match='use toffee'):
        collect(None,[Item(Marker(reason='partial',residual='R-09'))])


def test_uncertain_report_is_not_pass_but_does_not_imply_execution_failure(tmp_path):
    write(tmp_path/'run.json',{'status':'UNCERTAIN','mixed_baseline':False,'suites':[
        {'suite':'ifu','baseline':'b','inherited_from':'ucv.json'}],
        'tasks':[{'suite':'ifu','scope':'suite','cases':'cases.json'}]})
    write(tmp_path/'cases.json',{'cases':{
            'tests/test_partial.py::test_partial':{'verdict':'UNCERTAIN',
                'uncertain':{'reason':'oracle not confirmed','reference':'design/7'}}},
        'collected':['tests/test_partial.py::test_partial'],'collect_only':False})
    value=report(tmp_path)
    assert value['hardware_verdict']=='UNCERTAIN'
    assert value['counts']=={'UNCERTAIN':1}
    assert value['gaps']==[]
    assert value['uncertain']==[{'suite':'ifu','nodeid':'tests/test_partial.py::test_partial',
                               'reason':'oracle not confirmed','reference':'design/7'}]


@pytest.mark.parametrize('workers',[1,2])
def test_ucv_consumes_toffee_outcomes_and_receipts(tmp_path,workers):
    import os
    from pathlib import Path
    import subprocess
    import sys
    import json
    outcomes=pytest.importorskip('toffee.outcomes',reason='requires uc-toffee >= 2.1 with UNCERTAIN')
    assert verdict is outcomes.case_status
    test=tmp_path/'test_sample.py'
    test.write_text('''
import pytest
@pytest.mark.uncertain(reason="consumer contract pending", reference="project/note")
def test_pending():
    assert 1 + 1 == 2
''')
    source=str(Path(__file__).resolve().parents[1]/'src')
    env={**os.environ,'PYTHONPATH':os.pathsep.join(filter(None,(source,os.environ.get('PYTHONPATH')))),
         'PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1','UCV_CASE_DIR':str(tmp_path/'receipts')}
    result=subprocess.run([sys.executable,'-m','toffee','run',str(test),
                           '--workers',str(workers),'--output',str(tmp_path/'toffee'),
                           '-p','ucv.pytest_plugin','-q'],
                          cwd=tmp_path,env=env,text=True,capture_output=True,timeout=60)
    assert result.returncode==0,result.stdout+result.stderr
    cases=json.loads((tmp_path/'receipts/cases.json').read_text())
    manifest=json.loads((tmp_path/'toffee/manifest.json').read_text())
    assert cases['counts']==manifest['tests']=={'UNCERTAIN':1}
    row=next(iter(cases['cases'].values()))
    assert row['uncertain']=={'reason':'consumer contract pending','reference':'project/note'}
    assert manifest['uncertain'][0]['reason']==row['uncertain']['reason']
    assert '1 uncertain' in result.stdout and '1 passed' not in result.stdout


@pytest.mark.parametrize('mismatch',[None,'counts','declaration'])
def test_report_cross_checks_native_toffee_counts_and_reasons(tmp_path,mismatch):
    write(tmp_path/'run.json',{'status':'UNCERTAIN','mixed_baseline':False,
        'suites':[{'suite':'ifu','baseline':'b','inherited_from':'ucv.json'}],
        'tasks':[{'suite':'ifu','scope':'suite','cases':'cases.json','output':'ifu'}]})
    write(tmp_path/'cases.json',{'cases':{'test_x.py::test_x':{
        'verdict':'UNCERTAIN','uncertain':{'reason':'incomplete oracle'}}},
        'collected':['test_x.py::test_x'],'collect_only':False})
    write(tmp_path/'ifu/manifest.json',{'state':'committed','coverage_complete':True,
        'tests':{'PASS':1} if mismatch=='counts' else {'UNCERTAIN':1},
        'uncertain':[{'nodeid':'test_x.py::test_x',
                      'reason':'changed reason' if mismatch=='declaration' else 'incomplete oracle'}],
        'artifacts':[]})
    value=report(tmp_path)
    assert value['hardware_verdict']==('INCOMPLETE' if mismatch else 'UNCERTAIN')
    assert bool(value['gaps'])==bool(mismatch)


@pytest.mark.parametrize('status,hardware,expected',[
    ('PASS','PASS',0),('UNCERTAIN','UNCERTAIN',0),('FAIL','FAIL',1),
    ('ERROR','INCOMPLETE',1),('UNCERTAIN','INCOMPLETE',1),('PASS','INCOMPLETE',1)])
def test_ucv_run_exit_code_keeps_uncertainty_and_integrity_separate(
        tmp_path,monkeypatch,status,hardware,expected):
    from types import SimpleNamespace
    import ucv.cli as cli
    import ucv.report as reporting
    import ucv.run as running
    monkeypatch.setattr(cli,'Project',lambda root:SimpleNamespace(select=lambda *args:[]))
    monkeypatch.setattr(running,'run',lambda *args:(tmp_path,{'status':status}))
    monkeypatch.setattr(reporting,'report',lambda output:{'hardware_verdict':hardware})
    assert cli.main(['run','ifu'])==expected


@pytest.mark.parametrize('workers',[1,2])
def test_ifu_feature_reports_consume_complete_case_outcomes(tmp_path,workers):
    import json
    import os
    from pathlib import Path
    import subprocess
    import sys

    pytest.importorskip('toffee.outcomes',reason='requires uc-toffee >= 2.1 with UNCERTAIN')
    source=Path(__file__).resolve().parents[1]
    write(tmp_path/'verification_plan.json',{'version':1,'features':[
        {'id':f'IFU-TOP-00{index}','component':'Ifu',
         'title':f'contract {index}','description':'independent evidence classification'}
        for index in (1,2,3)],'residuals':[
            {'id':'R-09','behavior':'not every field observed','category':'unproven-scope',
             'evidence':'test_partial','owner':'test','next_action':'add observation',
             'blocking':False,'acceptance':'accepted-limited'}]})
    (tmp_path/'conftest.py').write_text('pytest_plugins=("suites.frontend.ifu.pytest_plugin",)\n')
    test=tmp_path/'test_feature.py'
    test.write_text('''
import pytest
@pytest.fixture
def broken_teardown():
    yield
    raise RuntimeError("teardown error")
@pytest.mark.feature("IFU-TOP-001")
def test_full(): assert True
@pytest.mark.feature("IFU-TOP-002")
@pytest.mark.uncertain(reason="not every field observed", reference="R-09")
def test_partial(): assert True
@pytest.mark.feature("IFU-TOP-003")
@pytest.mark.uncertain(reason="not every field observed", reference="R-09")
def test_error(broken_teardown): assert True
''')
    env={**os.environ,'PYTHONPATH':str(source),'PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1'}
    result=subprocess.run([sys.executable,'-m','toffee','run',str(test),
                           '--workers',str(workers),'--output',str(tmp_path/'toffee'),'-q'],
                          cwd=tmp_path,env=env,text=True,capture_output=True,timeout=60)
    assert result.returncode==1,result.stdout+result.stderr
    feature_report=json.loads((tmp_path/'results/feature-points.json').read_text())
    features=feature_report['features']
    assert [row['status'] for row in features]==['PASS','UNCERTAIN','ERROR']
    assert features[1]['tests'][0]['uncertain']=={
        'reason':'not every field observed','reference':'R-09'}
    assert 'uncertain' not in features[2]['tests'][0]
    manifest=json.loads((tmp_path/'toffee/manifest.json').read_text())
    assert manifest['tests']=={'PASS':1,'UNCERTAIN':1,'ERROR':1}
    assert feature_report['consistency_errors']==[]
