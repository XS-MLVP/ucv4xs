"""Agent for ICacheMetaInterleavedBank.

Same waiting discipline as the other SRAM-backed DUT: drive a level, wait for the
macro to accept it (the should-reset sequence clears one set per cycle), then
read the array back and compare with the reference model.

The SRAM wrappers' BIST inputs are held low: the design is used in functional
mode, and leaving them floating would put the macro into a test mode.
"""

from __future__ import annotations

from typing import Any

from toffee import ClockCycles
from toffee import Execution
from toffee.signals import sample_signal

from icacheverify.common.bist import BistBank
from icacheverify.common.driver.level import LevelDriver
from icacheverify.metabank.bundle.ports import MetaBankPorts
from icacheverify.metabank.model.bank import MetaBankModel
from icacheverify.metabank.model.bank import MetaEntry
from icacheverify.metabank.model.bank import MetaWay


RESET_MARGIN = 32
NUM_SETS = 128
NUM_WAYS = 4


class MetaBankAgent:
    def __init__(self, dut: Any, *, sets: int = NUM_SETS, ways: int = NUM_WAYS) -> None:
        self.dut = dut
        self.ports = MetaBankPorts.bind(dut)
        self.model = MetaBankModel(sets, ways)
        self.read_driver = LevelDriver(self.ports.read)
        self.bist = BistBank(dut, ("",))
        self.write_driver = LevelDriver(self.ports.write)
        self.flush_driver = LevelDriver(self.ports.flush_all)
        for leaf in self.ports.idle_leaves:
            leaf.Set(0)
            leaf.AsRiseWrite()
        self._execution: Execution | None = None

    # -- lifecycle ----------------------------------------------------------
    async def start(self, execution: Execution) -> "MetaBankAgent":
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
        self.read_driver.set({"valid": 0, "setIdx": 0})
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
        self.model = MetaBankModel(self.model.sets, self.model.ways)

    # -- observation --------------------------------------------------------
    @staticmethod
    def _bit(signal: Any) -> int:
        return int(sample_signal(signal).as_int()) & 1

    def read_ready(self) -> int:
        return self._bit(self.ports.read_ready.bits["ready"])

    def write_ready(self) -> int:
        return self._bit(self.ports.write_ready.bits["ready"])

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

    def read_entries(self) -> tuple[MetaWay, ...]:
        return tuple(
            MetaWay(
                valid=int(sample_signal(entry["valid"]).as_int()) & 1,
                entry=MetaEntry(
                    phy_tag=int(sample_signal(entry["bits"]["meta"]["phyTag"]).as_int()),
                    maybe_rvc_map=int(
                        sample_signal(entry["bits"]["meta"]["maybeRvcMap"]).as_int()),
                    code=int(sample_signal(entry["bits"]["code"]).as_int()) & 1,
                ),
            )
            for entry in self.ports.response
        )

    def settle_cycles(self) -> int:
        return self.model.sets + RESET_MARGIN

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

    async def read(self, set_index: int) -> tuple[MetaWay, ...]:
        self.read_driver.set({"valid": 1, "setIdx": set_index})
        await self.wait_for(lambda: self.read_ready() == 1, what="read ready")
        await self._edge()
        self.read_driver.set({"valid": 0, "setIdx": 0})
        expected = self.model.read(set_index)
        values = self.read_entries()
        for _ in range(self.settle_cycles()):
            await self._edge()
            values = self.read_entries()
            if len(values) == len(expected) and all(
                    self._same_way(got, want)
                    for got, want in zip(values, expected)):
                break
        return values

    @staticmethod
    def _same_way(got: MetaWay, want: MetaWay) -> bool:
        """A way only takes part in a hit while it is valid.

        The tag array and the validity array are separate storages, so an
        invalid way keeps whatever word was last written there.  Comparing that
        payload would flag stale storage that the pipeline never observes; the
        comparison therefore checks ``valid`` always and the payload only when
        the way is valid.
        """
        if got.valid != want.valid:
            return False
        return want.valid == 0 or got.entry == want.entry

    async def check_read(self, set_index: int) -> tuple[MetaWay, ...]:
        expected = self.model.read(set_index)
        actual = await self.read(set_index)
        if len(actual) != len(expected) or not all(
                self._same_way(got, want)
                for got, want in zip(actual, expected)):
            raise AssertionError(
                f"set {set_index}: bank returned {actual} != model {expected}")
        return actual

    async def flush_all(self) -> None:
        self.flush_driver.set({"flushAll": 1})
        await self._edge()
        await self._edge()
        self.flush_driver.set({"flushAll": 0})
        self.model.flush_all()
        await self._edge()

    # -- generic low-level helpers for hazard tests -------------------------
    def start_write(self, set_index: int, waymask: int, phy_tag: int = 0) -> None:
        self.write_driver.set({"valid": 1, "setIdx": set_index, "waymask": waymask,
                               "phyTag": phy_tag, "maybeRvcMap": 0, "code": 0})

    def stop_write(self) -> None:
        self.write_driver.set({"valid": 0, "setIdx": 0, "waymask": 0,
                               "phyTag": 0, "maybeRvcMap": 0, "code": 0})
