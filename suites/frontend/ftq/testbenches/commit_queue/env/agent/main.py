"""SDK-driven commit slots, lossless dual-phase checks and exact UID closure."""

from __future__ import annotations

from typing import Sequence
from contextlib import AsyncExitStack

from toffee import DriveStable, RisingEdge

from suites.frontend.ftq.testbenches.commit_queue.env.bundle.ports import CommitQueuePorts
from suites.frontend.ftq.testbenches.commit_queue.checker.transactions import CommitTransactions
from suites.frontend.ftq.testbenches.commit_queue.env.driver import CommitInputDriver
from suites.frontend.ftq.testbenches.commit_queue.env.monitor.decode import CommitMonitor
from suites.frontend.ftq.testbenches.commit_queue.transactions.types import EMPTY
from suites.frontend.ftq.testbenches.commit_queue.transactions.types import Input
from suites.frontend.ftq.testbenches.commit_queue.transactions.types import lane_rows
from suites.frontend.ftq.testbenches.shared.env.harness import Dut
from suites.frontend.ftq.testbenches.ftq.model import CallRet


class CommitQueueAgent:
    def __init__(self, dut: Dut) -> None:
        self.dut = dut
        self.ports = CommitQueuePorts.bind(dut)
        self.commit_driver = CommitInputDriver(dut.dut.clock, self.ports)
        self.before_monitor = CommitMonitor(DriveStable(dut.dut.clock), dut, self.ports)
        self.training_monitor = CommitMonitor(RisingEdge(dut.dut.clock), dut, self.ports)
        self.checker = CommitTransactions()
        self._started = False
        self._used = self._busy = self._failed = self._finished = False
        self._staged = EMPTY
        self._stack = None
        self._slot = 0
        self._last_tick = None
        self._inflight = None

    async def start(self) -> "CommitQueueAgent":
        if self._used:
            raise RuntimeError('CommitQueue agent cannot be restarted')
        self._used = True
        if self.dut._execution is None:
            raise RuntimeError('CommitQueue requires its fixture-managed Execution')
        stack = AsyncExitStack()
        try:
            await stack.enter_async_context(self.commit_driver.holding(self.dut._execution))
            await stack.enter_async_context(self.before_monitor.start(self.dut._execution))
            await stack.enter_async_context(self.training_monitor.start(self.dut._execution))
            self._stack = stack
            self._started = True
            await self.reset()
        except BaseException:
            await stack.aclose()
            self._started = False
            raise
        return self

    async def aclose(self) -> None:
        # Cleanup never claims completion and never clears the lifecycle ledger.
        # The fixture calls finish only for a passing body, before closing.
        try:
            if self._stack is not None:
                await self._stack.aclose()
        finally:
            self._stack = None
            self._started = False

    def _enter_work(self):
        if not self._started:
            raise RuntimeError('CommitQueue agent is not running')
        if self._busy:
            raise RuntimeError('concurrent CommitQueue input work is not supported')
        if self._failed:
            raise RuntimeError('CommitQueue has unreconciled input work after failure/cancellation')
        if self._finished:
            raise RuntimeError('CommitQueue input stream is finished')
        self.checker.require_clean()
        self._busy = True

    async def _cycle(self, rows=EMPTY, *, reset=False):
        self._slot += 1
        frame = Input(self._slot, rows, reset)
        self._inflight = frame
        event = await self.commit_driver.send(frame)
        before = await self.before_monitor.recv()
        after = await self.training_monitor.recv()
        assert before.event.tick + 1 == event.tick == after.event.tick, 'commit_queue stale/missing phase snapshot'
        if self._last_tick is not None:
            assert event.tick == self._last_tick + 2, 'commit_queue skipped/repeated input slot'
        self._last_tick = event.tick
        self.checker.advance_slot(frame, before.value, after.value, event.tick)
        self.before_monitor.record(before.value.head)
        self.training_monitor.record(after.value.head)
        self._inflight = None
        return after.value.head

    async def reset(self) -> None:
        self._enter_work()
        try:
            self._staged = EMPTY
            for _ in range(2):
                await self._cycle(reset=True)
            for _ in range(2):
                await self._cycle()
        except BaseException:
            self._failed = True
            raise
        finally:
            self._busy = False

    def _encode(self, rows: Sequence[CallRet | None]) -> dict[str, int]:
        if len(rows) != len(self.ports.backend):
            raise ValueError(f"expected {len(self.ports.backend)} lanes, got {len(rows)}")
        values: dict[str, int] = {}
        for lane, row in enumerate(rows):
            if row is not None and type(row) is not CallRet:
                raise ValueError('commit lanes require validated CallRet transactions or None')
            values[f"{lane}.valid"] = int(row is not None)
            values[f"{lane}.ras"] = 0 if row is None else row.ras
            values[f"{lane}.ptr"] = 0 if row is None else row.ptr
        return values

    async def drive(self, rows: Sequence[CallRet | None]) -> None:
        """Stage valid-only lanes; each subsequent requested edge is a new offer."""
        rows = lane_rows(rows)
        self._enter_work()
        try:
            self._staged = rows
        finally:
            self._busy = False

    async def release(self) -> None:
        self._enter_work()
        try:
            self._staged = EMPTY
        finally:
            self._busy = False

    async def step(self, cycles: int = 1) -> None:
        if type(cycles) is not int or cycles < 1:
            raise ValueError('CommitQueue step requires a positive integer cycle budget')
        self._enter_work()
        try:
            for _ in range(cycles):
                await self._cycle(self._staged)
        except BaseException:
            self._failed = True
            raise
        finally:
            self._busy = False

    def training(self) -> CallRet | None:
        return self.training_monitor.latest

    async def submit(self, rows: Sequence[CallRet | None]) -> CallRet | None:
        """Drive a commit cycle, take the edge, and compare with the FIFO model."""

        self._encode(rows)  # Reject before changing the oracle or any driver.
        rows = lane_rows(rows)
        self._enter_work()
        try:
            if any(self._staged):
                raise RuntimeError('release held CommitQueue input before submit')
            return await self._cycle(rows)
        except BaseException:
            self._failed = True
            raise
        finally:
            self._busy = False

    async def tick(self, *, expected: CallRet | None = None) -> CallRet | None:
        """Advance one edge with the current (already driven) lanes."""

        await self.step(1)
        observed = self.training()
        if expected is not None:
            try:
                self.checker.check(expected, observed)
            except BaseException:
                self._failed = True
                raise
        return observed

    def receipt(self):
        if self._failed or self._inflight is not None:
            raise RuntimeError('CommitQueue has unreconciled input work after failure/cancellation')
        return self.checker.receipt()

    async def finish(self, cycles=66):
        if self._finished:
            return self.receipt()
        if type(cycles) is not int or cycles < 2:
            raise ValueError('CommitQueue finish needs at least two idle observation cycles')
        self._enter_work()
        try:
            if any(self._staged):
                raise AssertionError('commit_queue producer remains armed; explicitly release before finish')
            quiet = 0
            for _ in range(cycles):
                await self._cycle()
                self.checker.audit()
                quiet = quiet + 1 if not self.checker.pending else 0
                if quiet >= 2:
                    break
            else:
                raise AssertionError('commit_queue finish budget exhausted with accepted work')
            assert not self.checker.pending, 'commit_queue accepted work did not complete'
            self._finished = True
            return self.receipt()
        except BaseException:
            self._failed = True
            raise
        finally:
            self._busy = False
