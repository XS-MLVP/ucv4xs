"""CommitQueue agent: lanes, scheduling guard, and FIFO checker."""

from __future__ import annotations

from typing import Sequence

from suites.frontend.ftq.commit_queue.bundle.ports import CommitQueuePorts
from suites.frontend.ftq.commit_queue.checker.model import CommitChecker
from suites.frontend.ftq.commit_queue.monitor.decode import decode_training
from suites.frontend.ftq.drivers.signal import Driver
from suites.frontend.ftq.drivers.signal import PulseDriver
from suites.frontend.ftq.drivers.signal import ResetDriver
from suites.frontend.ftq.monitors.cycle import EdgeMonitor
from suites.frontend.ftq.ports import Pins
from suites.frontend.ftq.harness import Dut
from suites.frontend.ftq.oracle import CallRet


class CommitQueueAgent:
    def __init__(self, dut: Dut) -> None:
        self.dut = dut
        self.ports = CommitQueuePorts.bind(dut)
        self.reset_driver = ResetDriver(
            dut, Pins(dut, {"reset": "reset"}, name="commit_queue.reset"))
        names = {}
        for lane, group in enumerate(self.ports.backend):
            for logical, pin in group.names.items():
                names[f"{lane}.{logical}"] = pin
        self.commit_driver = Driver(dut, Pins(dut, names, name="commit_queue.backend"))
        self.training_monitor = EdgeMonitor(
            "commit_queue.training", lambda d: decode_training(d, self.ports.train))
        self.checker = CommitChecker()
        self._started = False

    async def start(self) -> "CommitQueueAgent":
        if self._started:
            raise RuntimeError("CommitQueue agent already started")
        self.dut.add_monitor(self.training_monitor)
        self._started = True
        return self

    async def aclose(self) -> None:
        self.training_monitor.clear()
        self.commit_driver.close()
        self.reset_driver.pins.set(reset=0)
        self._started = False

    async def reset(self) -> None:
        self.commit_driver.pins.set(**{f"{lane}.valid": 0 for lane in range(8)})
        await self.reset_driver.send()
        self.training_monitor.clear()
        self.checker = CommitChecker()

    def _encode(self, rows: Sequence[CallRet | None]) -> dict[str, int]:
        if len(rows) != len(self.ports.backend):
            raise ValueError(f"expected {len(self.ports.backend)} lanes, got {len(rows)}")
        values: dict[str, int] = {}
        for lane, row in enumerate(rows):
            values[f"{lane}.valid"] = int(row is not None)
            values[f"{lane}.ras"] = 0 if row is None else row.ras
            values[f"{lane}.ptr"] = 0 if row is None else row.ptr
        return values

    async def drive(self, rows: Sequence[CallRet | None]) -> None:
        """Present one commit cycle; the caller owns the following edge."""

        self.commit_driver.pins.set(**self._encode(rows))
        self.dut.refresh()

    async def release(self) -> None:
        self.commit_driver.pins.set(**{f"{lane}.valid": 0 for lane in range(8)})
        self.dut.refresh()

    async def step(self, cycles: int = 1) -> None:
        await self.dut.edge(cycles)

    def training(self) -> CallRet | None:
        return self.training_monitor.sample(self.dut)

    async def submit(self, rows: Sequence[CallRet | None]) -> CallRet | None:
        """Drive a commit cycle, take the edge, and compare with the FIFO model."""

        expected = self.checker.step(rows)
        await self.drive(rows)
        await self.step(1)
        observed = self.training()
        self.checker.check(expected, observed)
        return observed

    async def tick(self, *, expected: CallRet | None = None) -> CallRet | None:
        """Advance one edge with the current (already driven) lanes."""

        await self.step(1)
        observed = self.training()
        if expected is not None:
            self.checker.check(expected, observed)
        return observed
