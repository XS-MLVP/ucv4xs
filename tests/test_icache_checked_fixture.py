"""Reported FAIL/ERROR cleanup and swallowed-failure strict finish controls."""
from types import SimpleNamespace
from pathlib import Path
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
import pytest
from suites.frontend.icache.runtime.fixtures import close_checked_agent

pytestmark = pytest.mark.asyncio


class Agent:
    def __init__(self, *, finish_error=None, close_error=None):
        self.finish_error, self.close_error = finish_error, close_error
        self.events = []

    async def finish(self):
        self.events.append('finish')
        if self.finish_error:
            raise self.finish_error

    async def aclose(self):
        self.events.append('close')
        if self.close_error:
            raise self.close_error


@pytest.mark.parametrize('reports', ({}, {'call': 'passed'}, {'setup': 'passed'}))
async def test_passing_or_missing_body_report_cannot_waive_strict_finish(reports):
    error = AssertionError('swallowed physical failure')
    agent = Agent(finish_error=error)
    request = SimpleNamespace(node=SimpleNamespace(_icache_body_reports=reports))
    with pytest.raises(AssertionError) as caught:
        await close_checked_agent(agent, request)
    assert caught.value is error and agent.events == ['finish', 'close']


@pytest.mark.parametrize('reports', ({'call': 'failed'}, {'call': 'skipped'}, {'setup': 'failed'}))
async def test_reported_nonpassing_body_is_not_duplicated_as_finish_teardown_error(reports):
    agent = Agent(finish_error=AssertionError('already observed physical failure'))
    request = SimpleNamespace(node=SimpleNamespace(_icache_body_reports=reports))
    await close_checked_agent(agent, request)
    assert agent.events == ['close']


async def test_independent_cleanup_error_still_propagates_after_reported_body_failure():
    error = RuntimeError('independent resource release failure')
    agent = Agent(finish_error=AssertionError('old'), close_error=error)
    request = SimpleNamespace(node=SimpleNamespace(_icache_body_reports={'call': 'failed'}))
    with pytest.raises(RuntimeError) as caught:
        await close_checked_agent(agent, request)
    assert caught.value is error


async def test_passing_body_retains_both_independent_finish_and_cleanup_errors():
    expected = (AssertionError('unfinished UID'), RuntimeError('resource error'))
    agent = Agent(finish_error=expected[0], close_error=expected[1])
    request = SimpleNamespace(node=SimpleNamespace())
    with pytest.raises(BaseExceptionGroup) as caught:
        await close_checked_agent(agent, request)
    assert caught.value.exceptions == expected


async def test_real_pytest_report_hook_and_fixture_bridge_keep_the_original_verdicts(tmp_path):
    # Exercise the actual async-yield fixture and makereport hook, with a fake
    # resource owner. This is framework-boundary evidence, not native RTL credit.
    (tmp_path / 'pytest.ini').write_text('[pytest]\nasyncio_mode=auto\nasyncio_default_fixture_loop_scope=function\n')
    (tmp_path / 'conftest.py').write_text('''
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from suites.frontend.icache.runtime import fixtures
from suites.frontend.icache.pytest_plugins import runtime
runtime.validate_runtime=lambda:None
pytest_plugins=('suites.frontend.icache.pytest_plugins.runtime',)

class Backend:
    def __init__(self,*args):pass
    def close(self):pass
class Execution:
    def __init__(self,*args,**kwargs):pass
    async def __aenter__(self):return self
    async def __aexit__(self,*args):pass
class Agent:
    def __init__(self,dut):
        self.failure=None;self.cleanup_failure=None;self.events=[]
    async def start(self,execution):pass
    async def finish(self):
        self.events.append('finish')
        if self.failure:raise self.failure
    async def aclose(self):
        self.events.append('close')
        Path(self.name+'.json').write_text(json.dumps(self.events))
        if self.cleanup_failure:raise self.cleanup_failure
@pytest.fixture
def dut_factory(monkeypatch):
    monkeypatch.setattr(fixtures,'Execution',Execution)
    monkeypatch.setattr(fixtures,'XCommClockBackend',Backend)
    return SimpleNamespace(create=lambda *args,**kwargs:SimpleNamespace(GetXClock=lambda:None))
checked_agent=fixtures.agent_fixture('fake',Agent,max_batch_ticks=1,checked=True)
''')
    (tmp_path / 'test_bridge.py').write_text('''
import pytest
async def test_pass(checked_agent):
    checked_agent.name='pass'
async def test_swallowed(checked_agent):
    checked_agent.name='swallowed';checked_agent.failure=AssertionError('swallowed physical error')
async def test_call_fail(checked_agent):
    checked_agent.name='call_fail';checked_agent.failure=AssertionError('old physical error')
    raise AssertionError('original body failure')
async def test_independent_cleanup(checked_agent):
    checked_agent.name='independent';checked_agent.cleanup_failure=RuntimeError('independent release error')
    raise AssertionError('original body failure')
''')
    root = Path(__file__).resolve().parents[1]
    environment = dict(os.environ, PYTHONPATH=os.pathsep.join((str(root), str(root / 'src'))))
    result = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-c', str(tmp_path / 'pytest.ini'),
        '--junitxml=' + str(tmp_path / 'outcomes.xml'), str(tmp_path / 'test_bridge.py')],
        cwd=tmp_path, env=environment, text=True, capture_output=True, timeout=60)
    assert result.returncode == 1, result.stdout + result.stderr
    suites = ET.parse(tmp_path / 'outcomes.xml').getroot()
    assert sum(int(suite.get('failures', 0)) for suite in suites) == 2
    assert sum(int(suite.get('errors', 0)) for suite in suites) == 2
    for name, expected in (('pass', ['finish', 'close']), ('swallowed', ['finish', 'close']),
                           ('call_fail', ['close']), ('independent', ['close'])):
        assert json.loads((tmp_path / (name + '.json')).read_text()) == expected
