"""Agent for ICacheMetaArray.

The array wraps two interleaved banks, so a double-line read must come back in
request order no matter which bank served each line. The agent drives levels,
waits for the macro to accept them (the should-reset sequence clears one set per
cycle), and compares the response against the model keyed by *set index*, not by
bank - a bank mix-up would then show up as data appearing on the wrong line.
"""

from __future__ import annotations

from typing import Any

from toffee import ClockCycles
from toffee import Execution
from toffee.signals import sample_signal

from suites.frontend.icache.bist import BistBank
from suites.frontend.icache.drivers.level import LevelDriver
from suites.frontend.icache.metaarray.bundle.ports import MetaArrayPorts
from suites.frontend.icache.metaarray.model.array import MetaArrayModel
from suites.frontend.icache.metaarray.model.array import MetaEntry
from suites.frontend.icache.metaarray.model.array import MetaWay


RESET_MARGIN = 48
NUM_SETS = 256
NUM_WAYS = 4
BANKS = 2


class MetaArrayAgent:
    def __init__(self, dut: Any, *, sets: int = NUM_SETS, ways: int = NUM_WAYS,
                 banks: int = BANKS) -> None:
        self.dut = dut
        self.ports = MetaArrayPorts.bind(dut)
        self.model = MetaArrayModel(sets, ways, banks)
        self.read_driver = LevelDriver(self.ports.read)
        self.bist = BistBank(dut, ("", "1"))
        self.write_driver = LevelDriver(self.ports.write)
        self.flush_driver = LevelDriver(self.ports.flush_all)
        for leaf in self.ports.idle_leaves:
            leaf.Set(0)
            leaf.AsRiseWrite()
        self._execution: Execution | None = None

    # -- lifecycle ----------------------------------------------------------
    async def start(self, execution: Execution) -> "MetaArrayAgent":
        self._execution = execution
        self.idle_inputs()
        await self.reset()
        return self

    async def aclose(self) -> None:
        for driver in (self.read_driver, self.write_driver, self.flush_driver):
            driver.close()
        self._execution = None

    def idle_inputs(self) -> None:
        self.bist.idle()
        self.read_driver.set({"valid": 0, "isDoubleLine": 0, "setIdx": (0, 0)})
        self.write_driver.set({"valid": 0, "setIdx": 0, "waymask": 0,
                               "phyTag": 0, "maybeRvcMap": 0, "code": 0})
        self.flush_driver.set({"flushAll": 0})

    async def _edge(self) -> None:
        await ClockCycles(self.dut.clock, 1)

    async def reset(self, cycles: int = 4) -> None:
        self.idle_inputs()
        self.dut.reset.Set(1)
        for _ in range(cycles):
            await self._edge()
        self.dut.reset.Set(0)
        for _ in range(2):
            await self._edge()
        self.model = MetaArrayModel(self.model.sets, self.model.ways,
                                    self.model.banks)

    # -- observation --------------------------------------------------------
    @staticmethod
    def _bit(signal: Any) -> int:
        return int(sample_signal(signal).as_int()) & 1

    def read_ready(self) -> int:
        return self._bit(self.ports.read_ready.bits["ready"])

    def write_ready(self) -> int:
        return self._bit(self.ports.write_ready.bits["ready"])

    def resp_lines(self) -> tuple[tuple[MetaWay, ...], ...]:
        return tuple(
            tuple(
                MetaWay(
                    valid=self._bit(way["valid"]),
                    entry=MetaEntry(
                        phy_tag=int(sample_signal(way["bits"]["meta"]["phyTag"]).as_int()),
                        maybe_rvc_map=int(
                            sample_signal(way["bits"]["meta"]["maybeRvcMap"]).as_int()),
                        code=self._bit(way["bits"]["code"]),
                    ),
                )
                for way in line
            )
            for line in self.ports.response
        )

    def settle_cycles(self) -> int:
        # Each bank clears one interleaved index per cycle, so the array needs
        # (sets / banks) cycles, plus margin for the pipeline.
        return self.model.sets // self.model.banks + RESET_MARGIN

    async def wait_for(self, predicate, *, what: str, cycles: int | None = None) -> None:
        cycles = self.settle_cycles() if cycles is None else cycles
        for _ in range(cycles):
            if predicate():
                return
            await self._edge()
        if not predicate():
            raise TimeoutError(f"{what} did not happen within {cycles} edges")

    # -- operations ---------------------------------------------------------
    async def write(self, set_index: int, waymask: int, *, phy_tag: int,
                    maybe_rvc_map: int = 0, code: int = 0) -> None:
        self.write_driver.set({
            "valid": 1, "setIdx": set_index, "waymask": waymask,
            "phyTag": phy_tag, "maybeRvcMap": maybe_rvc_map, "code": code,
        })
        await self.wait_for(lambda: self.write_ready() == 1, what="write ready")
        await self._edge()
        self.write_driver.set({"valid": 0, "setIdx": 0, "waymask": 0,
                               "phyTag": 0, "maybeRvcMap": 0, "code": 0})
        self.model.write(set_index, waymask, MetaEntry(phy_tag, maybe_rvc_map, code))
        await self._edge()

    async def bist_command(self, child: str = "", *, array: int = 0,
                           all_arrays: int = 0, readen: int = 1,
                           writeen: int = 0, be: int = 0, addr: int = 0,
                           addr_rd: int = 0, indata: int = 0,
                           hold: int = 2) -> tuple[int, int]:
        """Issue one MBIST command to one array instance of this DUT."""
        return await self.bist.command(
            self._edge, child, array=array, all_arrays=all_arrays,
            readen=readen, writeen=writeen, be=be, addr=addr,
            addr_rd=addr_rd, indata=indata, hold=hold)

    async def read(self, first: int, second: int | None = None) -> tuple[tuple[MetaWay, ...], ...]:
        """Single- or double-line read; returns lines in request order."""
        double = second is not None
        self.read_driver.set({
            "valid": 1,
            "isDoubleLine": 1 if double else 0,
            "setIdx": (first, second if double else first),
        })
        await self.wait_for(lambda: self.read_ready() == 1, what="read ready")
        await self._edge()
        self.read_driver.set({"valid": 0, "isDoubleLine": 0, "setIdx": (0, 0)})
        expected = self.model.read(first, second)
        values = self.resp_lines()
        for _ in range(self.settle_cycles()):
            await self._edge()
            values = self.resp_lines()
            if all(self._same_line(got, want)
                   for got, want in zip(values, expected)):
                break
        return values[:len(expected)]

    @staticmethod
    def _same_line(got, want) -> bool:
        """Invalid ways keep stale tag storage; only ``valid`` is contractual."""
        if len(got) != len(want):
            return False
        for got_way, want_way in zip(got, want):
            if got_way.valid != want_way.valid:
                return False
            if want_way.valid and got_way.entry != want_way.entry:
                return False
        return True

    async def check_read(self, first: int, second: int | None = None):
        expected = self.model.read(first, second)
        actual = await self.read(first, second)
        if len(actual) != len(expected) or not all(
                self._same_line(got, want)
                for got, want in zip(actual, expected)):
            raise AssertionError(
                f"read({first}, {second}): array returned {actual} != model {expected}")
        return actual

    async def flush_all(self) -> None:
        self.flush_driver.set({"flushAll": 1})
        await self._edge()
        await self._edge()
        self.flush_driver.set({"flushAll": 0})
        self.model.flush_all()
        await self._edge()

    # -- hazard helpers -----------------------------------------------------
    def start_write(self, set_index: int, waymask: int, phy_tag: int = 0) -> None:
        self.write_driver.set({"valid": 1, "setIdx": set_index, "waymask": waymask,
                               "phyTag": phy_tag, "maybeRvcMap": 0, "code": 0})

    def stop_write(self) -> None:
        self.write_driver.set({"valid": 0, "setIdx": 0, "waymask": 0,
                               "phyTag": 0, "maybeRvcMap": 0, "code": 0})
