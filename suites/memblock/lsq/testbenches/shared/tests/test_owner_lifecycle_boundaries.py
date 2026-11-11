"""Small controls for production constructor/consumer seams, without RTL."""
import asyncio
import json
from types import SimpleNamespace

import pytest

from suites.memblock.lsq import ROOT

pytestmark = pytest.mark.selftest


def test_real_owner_constructors_capacity_pipeline_and_replay_consumer():
    from suites.memblock.lsq.testbenches.vlq.env import VirtualLoadQueueEnv
    from suites.memblock.lsq.testbenches.vlq.transactions import Dispatch, Inputs, QueuePtr, Redirect, RobPtr, Writeback
    from suites.memblock.lsq.testbenches.rar.env import RarEnv
    from suites.memblock.lsq.testbenches.rar.transactions import Inputs as RarInputs, Query
    from suites.memblock.lsq.testbenches.replay.env import ReplayEnv
    from suites.memblock.lsq.testbenches.replay.transactions import Cause, Enqueue, Inputs as ReplayInputs, LqWakeup, Observation, ReplaySlot

    specs = json.loads((ROOT / "manifest/duts.json").read_text())["duts"]
    vlq = VirtualLoadQueueEnv("control", specs["virtual_load_queue"], None, None, None, None, None, None)
    idle = Inputs((Dispatch(),) * 8, (Writeback(),) * 3)
    vlq._update_ledger(Inputs((Dispatch(True, RobPtr.encode(2), QueuePtr(), 1),) + (Dispatch(),) * 7, idle.writebacks))
    assert vlq.entries[0].uid == 1
    vlq._update_ledger(Inputs(idle.dispatch, idle.writebacks, reset=True))
    for _ in range(5):
        vlq._update_ledger(idle)
    vlq._update_ledger(Inputs(idle.dispatch, idle.writebacks, Redirect(True, RobPtr.encode(2))))
    assert vlq.stall
    for expected_stall in (True, True, False):
        vlq._update_ledger(idle)
        assert vlq.stall == expected_stall

    rar = RarEnv("control", specs["load_queue_rar"], None, None, None, None, None, None)
    for group in range(32):
        queries = tuple(Query(True, RobPtr.encode(2 + group * 3 + lane), QueuePtr.encode(1),
                              0x8000 + (group * 3 + lane) * 64) for lane in range(3))
        rar._update_ledger(RarInputs(queries, (False,) * 3, (False,) * 3), SimpleNamespace(ready=(True,) * 3))
    assert len(rar.entries) == 96 and not rar.available
    with pytest.raises(AssertionError):
        rar._update_ledger(RarInputs(queries, (False,) * 3, (False,) * 3), SimpleNamespace(ready=(True,) * 3))

    replay = ReplayEnv(None, None, None, None, None, None)
    replay._update_ledger(ReplayInputs((replay.request(), Enqueue(), Enqueue())), Observation())
    owner = next(iter(replay.owners.values()))
    lane = owner.slot % 3
    uop = owner.request.uop
    visible = Observation(replay=tuple(ReplaySlot(True, owner.slot, uop.lq.flag, uop.lq.value, uop.checkpoint,
        uop.rob.flag, uop.rob.value, uop.rob.former, sq=uop.sq) if bank == lane else ReplaySlot()
                                      for bank in range(3)))
    replay.response = visible

    async def cycle(**fields):
        replay._update_ledger(ReplayInputs((Enqueue(),) * 3, **fields), visible)

    replay.cycle = cycle
    assert asyncio.run(replay.issue(owner.slot)) == (owner.slot, owner.uid)
    assert replay.owners[owner.slot].issued

    waiting = ReplayEnv(None, None, None, None, None, None)
    request = waiting.request(Cause.UNCACHE)
    waiting._update_ledger(ReplayInputs((request, Enqueue(), Enqueue())), Observation())
    owner = next(iter(waiting.owners.values()))
    waiting._update_ledger(ReplayInputs(nc=LqWakeup(True, request.uop.lq)), Observation())
    assert owner.blocked, "NC wakeup is not effective on its arrival edge"
    waiting._update_ledger(ReplayInputs(), Observation())
    assert not owner.blocked, "resident UNCACHE wait consumes the one-edge delayed wakeup"

    from suites.memblock.lsq.testbenches.lsq_wrapper.env import WrapperEnv
    wrapper = WrapperEnv(None, None, None, None, None, None, None, None, "scope-control")
    calls = []
    first = SimpleNamespace(observe=lambda *window: calls.append(("first", window)))
    second = SimpleNamespace(observe=lambda *window: calls.append(("second", window)))
    for checker in (first, second, first):
        with wrapper.checker_scope(checker):
            wrapper._observe_history("request")
        assert not wrapper._history_checkers
    assert [name for name, _ in calls] == ["first", "second", "first"]
    with pytest.raises(AssertionError):
        with wrapper.checker_scope(first):
            raise AssertionError("failed producer scope")
    assert not wrapper._history_checkers

    class RejectBeforeDrive:
        async def send(self, request):
            raise ValueError("deliberate rejected request")
    wrapper.driver = RejectBeforeDrive()
    before = len(calls)
    with wrapper.checker_scope(first, preserve_core_error=True):
        with pytest.raises(ValueError):
            asyncio.run(wrapper.cycle())
    assert first.core_error == "ValueError('deliberate rejected request')"
    assert len(calls) == before and not wrapper._history_checkers
