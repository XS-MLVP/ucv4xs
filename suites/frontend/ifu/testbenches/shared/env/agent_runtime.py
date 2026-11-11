"""Shared pytest-to-agent lifecycle bridge for IFU fixtures."""

from __future__ import annotations

from contextlib import asynccontextmanager
import sys


@asynccontextmanager
async def agent_runtime(request, agent):
    """Forward an already-reported pytest body outcome into its agent context.

    Async fixtures do not receive the test body's exception at their yield.
    Without this bridge a real checker FAIL is followed by an artificial
    teardown ERROR from strict finish. No verdict is changed here: pytest's
    existing setup/call report is authoritative, independent cleanup errors
    still propagate, and swallowed failures in a passing call still fail finish.
    """
    manager = agent.running()
    await manager.__aenter__()
    try:
        yield agent
    except BaseException:
        if not await manager.__aexit__(*sys.exc_info()):
            raise
    else:
        phases = getattr(request.config, '_ifu_phases', {}).get(request.node.nodeid, {})
        nonpassing = any(phases.get(phase, {}).get('outcome') in {'failed', 'skipped'}
                         for phase in ('setup', 'call'))
        if nonpassing:
            error = RuntimeError('pytest has already reported a nonpassing test body')
            await manager.__aexit__(type(error), error, None)
        else:
            await manager.__aexit__(None, None, None)
