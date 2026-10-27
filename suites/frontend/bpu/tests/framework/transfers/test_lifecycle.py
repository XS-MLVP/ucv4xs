from __future__ import annotations

import asyncio

import pytest
from toffee import TransferState
from toffee import XTransfer

from tests.framework.fakes import event


async def test_xtransfer_lifecycle_is_awaitable():
    transfer: XTransfer[str, int] = XTransfer("request")
    processing = asyncio.create_task(transfer.wait_processing())

    transfer.mark_processing(event(2))
    assert await processing == event(2)
    assert transfer.state is TransferState.PROCESSING

    transfer.complete(event(6), 42)
    assert await transfer == 42
    assert transfer.state is TransferState.COMPLETED
    assert transfer.accepted_event.tick == 2
    assert transfer.completed_event.tick == 6


async def test_xtransfer_rejects_invalid_transition():
    transfer: XTransfer[str, int] = XTransfer("request")
    with pytest.raises(RuntimeError, match="cannot complete"):
        transfer.complete(event(2), 42)
    transfer.cancel()
    assert transfer.state is TransferState.CANCELLED
    with pytest.raises(asyncio.CancelledError):
        await transfer


async def test_xtransfer_terminal_callback_runs_once():
    transfer: XTransfer[str, int] = XTransfer("request")
    completed = []
    transfer.add_done_callback(completed.append)
    transfer.mark_processing(event(2))
    transfer.complete(event(4), 7)
    transfer.cancel()

    assert completed == [transfer]
    late = []
    transfer.add_done_callback(late.append)
    assert late == [transfer]

