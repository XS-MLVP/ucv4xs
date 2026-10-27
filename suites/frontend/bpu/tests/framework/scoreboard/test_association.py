from __future__ import annotations

import asyncio

import pytest
from toffee import Execution
from toffee import MemoryBackend
from toffee import Scoreboard
from toffee import Transfer
from toffee import XTransfer

from tests.framework.fakes import TaggedRequest
from tests.framework.fakes import TaggedResponse
from tests.framework.fakes import event


class Driver:
    def submit(self, request):
        return XTransfer(request)


class Monitor:
    pass


@pytest.mark.feature("ENV-SCB-001")
async def test_fixed_latency_association_uses_accepted_event():
    clock = object()
    async with Execution(MemoryBackend(clock)) as execution:
        scoreboard = Scoreboard("latency").bind(
            execution,
            driver=Driver(),
            monitor=Monitor(),
            clock=clock,
            response_timeout_cycles=8,
            latency_cycles=2,
            manage_monitor=False,
        )
        transfer = XTransfer(TaggedRequest(1))
        transfer.mark_processing(event(10))

        matched = scoreboard.associate(
            Transfer(event(14), TaggedResponse(1)),
            (transfer,),
        )
        assert matched is transfer
        transfer.complete(event(14), TaggedResponse(1))
        await scoreboard.aclose()


@pytest.mark.feature("ENV-SCB-001")
async def test_key_association_can_complete_out_of_order():
    clock = object()
    async with Execution(MemoryBackend(clock)) as execution:
        scoreboard = Scoreboard("tagged").bind(
            execution,
            driver=Driver(),
            monitor=Monitor(),
            clock=clock,
            response_timeout_cycles=8,
            request_key=lambda request: request.tag,
            response_key=lambda response: response.tag,
            manage_monitor=False,
        )
        first = XTransfer(TaggedRequest(1))
        second = XTransfer(TaggedRequest(2))

        matched = scoreboard.associate(
            Transfer(event(2), TaggedResponse(2)),
            (first, second),
        )
        assert matched is second

        first.cancel()
        second.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        await scoreboard.aclose()
