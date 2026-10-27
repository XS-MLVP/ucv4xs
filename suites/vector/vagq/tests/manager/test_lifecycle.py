"""Intentional checker failure must escape Execution and release resources."""
import pytest

from vagqverify.env import manager_session
from vagqverify.manager.types import Allocation

pytestmark = pytest.mark.toffee_functional_coverage(False)


class InjectedComparisonFailure(AssertionError):
    pass


def leaves(error):
    if isinstance(error, BaseExceptionGroup):
        return [leaf for child in error.exceptions for leaf in leaves(child)]
    return [error]


async def test_capture_failure_is_not_swallowed_and_next_environment_is_clean(
    tmp_path, native_registration, monkeypatch
):
    def fail(**_):
        raise InjectedComparisonFailure('deliberate checker failure')

    with pytest.raises(BaseException) as caught:
        async with manager_session(tmp_path / 'failure', register=native_registration) as env:
            await env.agent.reset()
            monkeypatch.setattr(env.checker.board, 'check', fail)
            await env.agent.offer(1)
    assert any(isinstance(error, InjectedComparisonFailure) for error in leaves(caught.value))
    async with manager_session(tmp_path / 'recovery', register=native_registration) as env:
        await env.agent.reset()
        assert await env.agent.offer(1) == Allocation(1, 0, 1)
        await env.agent.stream([])
