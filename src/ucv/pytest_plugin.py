"""Lossless collection and verdict receipts, independent of coverage. MPL-2.0."""
from collections import Counter
import os
from pathlib import Path
import random
import pytest
from .common import digest, now, write

_config=None
_cases={}
_collected=[]

def pytest_configure(config):
    global _config, _cases, _collected
    _config=config; _cases={}; _collected=[]
    random.seed(int(os.environ.get('UCV_SEED','1')))

def pytest_collection_finish(session):
    global _collected
    _collected=[item.nodeid for item in session.items]

def pytest_xdist_node_collection_finished(node,ids):
    global _collected
    if _collected and _collected!=list(ids):
        raise pytest.UsageError('Worker collections differ')
    _collected=list(ids)

# This hook is optional when xdist is not installed/loaded.
pytest_xdist_node_collection_finished=pytest.hookimpl(optionalhook=True)(pytest_xdist_node_collection_finished)

def pytest_runtest_logreport(report):
    phases=_cases.setdefault(report.nodeid,{})
    phases[report.when]={'outcome':report.outcome,'duration':report.duration,
                         'wasxfail':getattr(report,'wasxfail',None)}

def verdict(phases):
    if any(p['outcome']=='failed' for k,p in phases.items() if k!='call'):return 'ERROR'
    call=phases.get('call',{})
    if call.get('outcome')=='failed':return 'FAIL'
    if any(p.get('wasxfail') for p in phases.values()):
        return 'XPASS' if call.get('outcome')=='passed' else 'XFAIL'
    if any(p['outcome']=='skipped' for p in phases.values()):return 'SKIP'
    if call.get('outcome')=='passed' and set(phases)=={'setup','call','teardown'}:return 'PASS'
    return 'INCOMPLETE'

@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session,exitstatus):
    if hasattr(session.config,'workerinput'):return
    directory=os.environ.get('UCV_CASE_DIR')
    if not directory:return
    cases={node:{'verdict':verdict(phases),'phases':phases} for node,phases in _cases.items()}
    for node in _collected:
        if node not in cases and not session.config.option.collectonly:
            cases[node]={'verdict':'INCOMPLETE','phases':{}}
    write(Path(directory)/'cases.json',{'collected':_collected,'collection_sha256':digest(_collected),
        'cases':cases,'counts':dict(Counter(c['verdict'] for c in cases.values())),
        'exit_code':int(exitstatus),'collect_only':bool(session.config.option.collectonly),'completed_at':now()})
