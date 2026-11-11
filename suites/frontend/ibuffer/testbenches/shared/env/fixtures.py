"""Cross-DUT Picker fixture mechanics; DUT plugins supply name and agent.

The DUT is constructed before the managed runner attaches its coverage file,
so each test starts with an explicit reset whose first active cycle follows
de-assertion.  Coverage discovery recognises the ``dut`` attribute and calls
``Finish`` before native aggregation.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
import sys

from suites.frontend.ibuffer.testbenches.shared.env.dut import DutHarness


@asynccontextmanager
async def agent_runtime(request, agent):
    """Forward a reported pytest body outcome into the agent context.

    Async fixtures do not receive the test body's exception at their yield.
    Without this bridge a real checker FAIL is followed by an artificial
    teardown ERROR from strict finish.  No verdict is changed here: pytest's
    setup/call report is authoritative and independent cleanup errors still
    propagate.
    """
    manager = agent.running()
    await manager.__aenter__()
    try:
        yield agent
    except BaseException:
        if not await manager.__aexit__(*sys.exc_info()):
            raise
    else:
        phases = getattr(request.config, "_ibuffer_phases", {}).get(
            request.node.nodeid, {})
        nonpassing = any(phases.get(phase, {}).get("outcome") in {"failed", "skipped"}
                         for phase in ("setup", "call"))
        if nonpassing:
            error = RuntimeError("pytest has already reported a nonpassing test body")
            await manager.__aexit__(type(error), error, None)
        else:
            await manager.__aexit__(None, None, None)


def _factory(request, tmp_path, monkeypatch, dut_name, agent_class):
    monkeypatch.chdir(tmp_path)
    opened = []

    def create():
        harness = DutHarness(dut_name)
        opened.append(harness)
        if getattr(request.config, "_toffee_managed_coverage", None) is not None:
            request.getfixturevalue("toffee_register_dut")(harness.dut)
        return agent_class(harness)

    try:
        yield create
    finally:
        for harness in opened:
            harness.finish()
