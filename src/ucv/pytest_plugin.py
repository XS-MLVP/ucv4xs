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

# Toffee owns UNCERTAIN, including pytest display and phase aggregation.  The
# official locked distribution (uc-toffee >= 2.1) exports both the vocabulary
# and the pytest adapter; keep the legacy adapter name for older development
# builds that used the local patch before it was released.
try:
    from toffee.outcomes import case_status as verdict, phase_record
except ImportError:
    phase_record=None

    def verdict(phases):
        if any(p['outcome']=='failed' for k,p in phases.items() if k!='call'):return 'ERROR'
        call=phases.get('call',{})
        if call.get('outcome')=='failed':return 'XPASS' if call.get('strict_xpass') else 'FAIL'
        if any(p.get('wasxfail') is not None for p in phases.values()):
            return 'XPASS' if call.get('outcome')=='passed' else 'XFAIL'
        if any(p['outcome']=='skipped' for p in phases.values()):return 'SKIP'
        if call.get('outcome')=='passed' and set(phases)=={'setup','call','teardown'}:return 'PASS'
        return 'INCOMPLETE'

from importlib.util import find_spec
if phase_record is not None:
    if find_spec('toffee._pytest_outcomes') is not None:
        pytest_plugins=('toffee._pytest_outcomes',)
    elif find_spec('toffee._outcomes') is not None:
        pytest_plugins=('toffee._outcomes',)

def pytest_configure(config):
    global _config, _cases, _collected
    _config=config; _cases={}; _collected=[]
    random.seed(int(os.environ.get('UCV_SEED','1')))

def pytest_collection_modifyitems(config,items):
    for item in items:
        if item.get_closest_marker('incomplete') is not None:
            raise pytest.UsageError(
                f'{item.nodeid}: use toffee @pytest.mark.uncertain(reason=..., reference=...); '
                'INCOMPLETE is reserved for unfinished execution')
        if phase_record is None and item.get_closest_marker('uncertain') is not None:
            raise pytest.UsageError(
                f'{item.nodeid}: installed Toffee lacks UNCERTAIN; run ucv setup with the locked uc-toffee')

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
    if phase_record is not None:
        phases[report.when]=phase_record(report)
    else:
        phases[report.when]={'outcome':report.outcome,'duration':report.duration,
                            'wasxfail':getattr(report,'wasxfail',None),
                            'strict_xpass':report.failed and str(report.longrepr).startswith('[XPASS(strict)]')}

@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session,exitstatus):
    if hasattr(session.config,'workerinput'):return
    directory=os.environ.get('UCV_CASE_DIR')
    if not directory:return
    cases={}
    for node,phases in _cases.items():
        row={'verdict':verdict(phases),'phases':phases}
        declaration=phases.get('call',{}).get('uncertain')
        if declaration:row['uncertain']=declaration
        cases[node]=row
    for node in _collected:
        if node not in cases and not session.config.option.collectonly:
            cases[node]={'verdict':'INCOMPLETE','phases':{}}
    write(Path(directory)/'cases.json',{'collected':_collected,'collection_sha256':digest(_collected),
        'cases':cases,'counts':dict(Counter(c['verdict'] for c in cases.values())),
        'exit_code':int(exitstatus),'collect_only':bool(session.config.option.collectonly),'completed_at':now()})
