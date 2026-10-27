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
