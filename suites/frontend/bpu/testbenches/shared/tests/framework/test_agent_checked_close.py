"""A swallowed error is still a passing body and must get strict finish."""
from types import SimpleNamespace
import pytest
from suites.frontend.bpu.testbenches.shared.env.fixtures import close_agent

pytestmark=pytest.mark.selftest


@pytest.mark.parametrize('reports,expected',(({},True),({'setup':'passed','call':'passed'},True),
    ({'setup':'failed'},False),({'call':'failed'},False),({'setup':'skipped'},False),({'call':'skipped'},False)))
async def test_actual_body_reports_control_only_normal_finish_not_cleanup(reports,expected):
    calls=[]
    async def close(**kwargs):calls.append(kwargs)
    await close_agent(SimpleNamespace(aclose=close),SimpleNamespace(node=SimpleNamespace(_bpu_body_reports=reports)),checked=True)
    assert calls==[dict(check=expected)]


@pytest.mark.parametrize('checked',(False,True))
async def test_independent_cleanup_error_is_never_suppressed(checked):
    error=OSError('independent resource-close failure')
    async def close(**kwargs):raise error
    with pytest.raises(OSError) as caught:
        await close_agent(SimpleNamespace(aclose=close),SimpleNamespace(node=SimpleNamespace(
            _bpu_body_reports={'call':'failed'})),checked=checked)
    assert caught.value is error
