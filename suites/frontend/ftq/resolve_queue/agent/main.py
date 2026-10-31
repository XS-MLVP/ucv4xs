"""ResolveQueue agent: owns drivers, monitors and the checker glue."""

from __future__ import annotations

from typing import Iterable
from typing import Sequence

from suites.frontend.ftq.drivers.signal import LevelDriver
from suites.frontend.ftq.drivers.signal import PulseDriver
from suites.frontend.ftq.drivers.signal import ResetDriver
from suites.frontend.ftq.monitors.cycle import EdgeMonitor
from suites.frontend.ftq.ports import Pins
from suites.frontend.ftq.harness import Dut
from suites.frontend.ftq.resolve_queue.bundle.ports import ResolveQueuePorts
from suites.frontend.ftq.resolve_queue.checker.model import ResolveChecker
from suites.frontend.ftq.resolve_queue.driver.encoding import encode
from suites.frontend.ftq.resolve_queue.monitor.decode import decode_training
from suites.frontend.ftq.resolve_queue.transaction.types import ResolveReport
from suites.frontend.ftq.resolve_queue.transaction.types import Training


def _union(dut: Dut, groups: Sequence[Pins], name: str) -> Pins:
    names = {}
    for index, group in enumerate(groups):
        for logical, pin in group.names.items():
            names[f"{index}.{logical}"] = pin
    return Pins(dut, names, name=name)


class ResolveQueueAgent:
    def __init__(self, dut: Dut) -> None:
        self.dut = dut
        self.ports = ResolveQueuePorts.bind(dut)
        self.reset_driver = ResetDriver(
            dut, Pins(dut, {"reset": "reset"}, name="resolve_queue.reset"))
        self.backend_driver = PulseDriver(
            dut, _union(dut, self.ports.backend, "resolve_queue.backend"))
        self.ifu_driver = PulseDriver(dut, self.ports.ifu)
        self.redirect_driver = PulseDriver(dut, self.ports.redirect)
        self.enqueue_driver = PulseDriver(dut, self.ports.enqueue)
        self.ready_driver = LevelDriver(
            dut, Pins(dut, {"ready": "io_bpuTrain_ready"}, name="resolve_queue.ready"))
        self.training_monitor = EdgeMonitor(
            "resolve_queue.training", lambda d: decode_training(d, self.ports.train))
        self.checker = ResolveChecker()
        self._started = False

    async def start(self) -> "ResolveQueueAgent":
        if self._started:
            raise RuntimeError("ResolveQueue agent already started")
        self.dut.add_monitor(self.training_monitor)
        self._started = True
        return self

    async def aclose(self) -> None:
        self.training_monitor.clear()
        self.ready_driver.close()
        self.enqueue_driver.close()
        self.redirect_driver.close()
        self.ifu_driver.close()
        self.backend_driver.close()
        self.reset_driver.pins.set(reset=0)
        self._started = False

    async def reset(self, *, asserted: int = 2, released: int = 2) -> None:
        await self.ready_driver.set({"ready": 0})
        await self.reset_driver.send(asserted=asserted, released=released)
        self.training_monitor.clear()
        self.checker = ResolveChecker()

    async def ready(self, enabled: bool = True) -> None:
        await self.ready_driver.set({"ready": int(enabled)})

    async def resolve(self, reports: Iterable[ResolveReport], *, source: str = "backend") -> None:
        """Drive one cycle of reports (backend lanes or IFU), then release."""

        reports = tuple(reports)
        if not reports:
            raise ValueError("resolve() needs at least one report")
        if source == "backend":
            if len(reports) > 3:
                raise ValueError("backend accepts at most three lane reports")
            encoded = {}
            for lane, report in enumerate(reports):
                for logical, value in encode(report).items():
                    encoded[f"{lane}.{logical}"] = value
            await self.backend_driver.send(encoded)
        elif source == "ifu":
            if len(reports) != 1:
                raise ValueError("IFU accepts exactly one resolve report")
            await self.ifu_driver.send(encode(reports[0]))
        else:
            raise ValueError(f"unknown source {source!r}")

    async def resolve_mixed(self, backend: Sequence[ResolveReport | None] = (),
                            ifu: ResolveReport | None = None) -> None:
        """Drive backend lanes and the IFU source in the same cycle.

        ``None`` entries leave that backend lane idle, so a caller can place a
        report in any specific lane instead of always starting at lane 0.
        """

        if len(backend) > 3:
            raise ValueError("backend accepts at most three lane reports")
        values = {}
        for lane, report in enumerate(backend):
            if report is None:
                continue
            for logical, value in encode(report).items():
                values[f"{lane}.{logical}"] = value
        if ifu is not None:
            self.ifu_driver.pins.set(**encode(ifu))
        if values:
            self.backend_driver.pins.set(**values)
        self.dut.refresh()
        await self.dut.edge(1)
        if values:
            for logical in values:
                self.dut.input(self.backend_driver.pins.physical(logical)).Set(0)
        if ifu is not None:
            self.ifu_driver.pins.set(valid=0)
        self.dut.refresh()
        await self.dut.edge(1)

    async def backend_lanes(self, lanes: Sequence[ResolveReport | None]) -> None:
        """Drive backend lanes with explicit valid/invalid payloads."""

        if len(lanes) != 3:
            raise ValueError("backend lane vector has exactly three entries")
        encoded: dict[str, int] = {}
        for lane, report in enumerate(lanes):
            if report is None:
                encoded[f"{lane}.valid"] = 0
                continue
            for logical, value in encode(report).items():
                encoded[f"{lane}.{logical}"] = value
        await self.backend_driver.send(encoded)

    async def redirect(self, index: int, flag: int = 0) -> None:
        await self.redirect_driver.send({"valid": 1, "flag": flag, "value": index})

    async def bpu_enqueue(self, index: int) -> None:
        await self.enqueue_driver.send({"valid": 1, "value": index})

    async def step(self, cycles: int = 1) -> None:
        await self.dut.edge(cycles)

    def training(self) -> Training | None:
        return self.training_monitor.sample(self.dut)

    def take_training(self) -> Training | None:
        value = self.training_monitor.latest
        self.training_monitor.latest = None
        return value

    async def wait_training(self, cycles: int = 8) -> Training:
        for _ in range(cycles):
            value = self.training()
            if value is not None:
                return value
            await self.step(1)
        raise AssertionError("ResolveQueue did not present a training entry")

    async def drain(self, *, cycles: int = 8) -> Training:
        value = await self.wait_training(cycles)
        await self.ready(True)
        await self.step(1)
        await self.ready(False)
        await self.step(1)
        return value

    # Ownership/identity observables; payload expectations come from the checker.
    def enq_ptr(self) -> int:
        return self.dut.internal("ResolveQueueDut_top.ResolveQueue.enqPtr_value")

    def deq_ptr(self) -> int:
        return self.dut.internal("ResolveQueueDut_top.ResolveQueue.deqPtr_value")
