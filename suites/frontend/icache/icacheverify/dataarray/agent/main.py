"""Agent for ICacheDataArray.

The array is a router plus eight data banks. The agent drives level inputs,
waits for the macro to accept them, and compares each request's response bank by
bank against the model. Because the model is keyed by (bank, set, way) and not by
request slot, a routing mistake shows up as data appearing in the wrong request
or the wrong bank.
"""

from __future__ import annotations

from typing import Any

from toffee import ClockCycles
from toffee import Execution
from toffee.signals import sample_signal

from icacheverify.common.bist import BistBank
from icacheverify.common.driver.level import LevelDriver
from icacheverify.dataarray.bundle.ports import DataArrayPorts
from icacheverify.dataarray.model.array import DataArrayModel
from icacheverify.dataarray.model.array import DataEntry
from icacheverify.dataarray.model.array import LineSelect
from icacheverify.dataarray.model.array import ReadRequest


RESET_MARGIN = 48
BANKS = 8
SETS = 256
WAYS = 4


class DataArrayAgent:
    def __init__(self, dut: Any, *, banks: int = BANKS, sets: int = SETS,
                 ways: int = WAYS) -> None:
        self.dut = dut
        self.ports = DataArrayPorts.bind(dut)
        self.model = DataArrayModel(banks, sets, ways)
        self.read_driver = LevelDriver(self.ports.read)
        self.bist = BistBank(dut, ("", "1", "2", "3", "4", "5", "6", "7"))
        self.write_driver = LevelDriver(self.ports.write)
        for leaf in self.ports.idle_leaves:
            leaf.Set(0)
            leaf.AsRiseWrite()
        self._execution: Execution | None = None

    # -- lifecycle ----------------------------------------------------------
    async def start(self, execution: Execution) -> "DataArrayAgent":
        self._execution = execution
        self.idle_inputs()
        await self.reset()
        return self

    async def aclose(self) -> None:
        for driver in (self.read_driver, self.write_driver):
            driver.close()
        self._execution = None

    def idle_inputs(self) -> None:
        self.bist.idle()
        self.read_driver.set(self._encode_read(()))
        self.write_driver.set({
            "valid": 0, "setIdx": 0, "waymask": 0,
            "entries": tuple({"data": 0, "code": 0} for _ in range(self.model.banks)),
        })

    def _encode_read(self, requests: tuple[ReadRequest, ...]) -> dict[str, Any]:
        encoded = []
        for index, request in enumerate(requests):
            # Each field is a two-entry Vec (one per line); an unused line is
            # padded so the bundle shape always matches the DUT.
            def pad(values: tuple[int, ...]) -> tuple[int, int]:
                return tuple(values) + (0,) * (2 - len(values))
            slot: dict[str, Any] = {
                "bankSel": pad(tuple(line.bank_mask for line in request.lines)),
                "vSetIdx": pad(tuple(line.set_index for line in request.lines)),
                "waymask": pad(tuple(line.waymask for line in request.lines)),
            }
            # Only the second request carries an explicit valid leaf; the first
            # is gated by the top-level read valid.
            if index == 1:
                slot["valid"] = 1
            encoded.append(slot)
        while len(encoded) < 2:
            encoded.append({
                "bankSel": (0, 0), "vSetIdx": (0, 0), "waymask": (0, 0),
                **({"valid": 0} if len(encoded) else {}),
            })
        return {"valid": 1 if requests else 0, "req": tuple(encoded)}

    async def _edge(self) -> None:
        await ClockCycles(self.dut.clock, 1)

    async def reset(self, cycles: int = 4) -> None:
        self.idle_inputs()
        self.dut.reset.Set(1)
        for _ in range(cycles):
            await self._edge()
        self.dut.reset.Set(0)
        await self._edge()
        await self._edge()
        self.model = DataArrayModel(self.model.banks, self.model.sets, self.model.ways)

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

    def responses(self) -> tuple[tuple[DataEntry, ...], ...]:
        return tuple(
            tuple(
                DataEntry(
                    data=int(sample_signal(data).as_int()),
                    code=self._bit(code),
                )
                for data, code in zip(response["datas"], response["codes"])
            )
            for response in self.ports.response
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
    async def write(self, set_index: int, waymask: int,
                    entries: tuple[DataEntry, ...]) -> None:
        if len(entries) != self.model.banks:
            raise ValueError(f"a write needs {self.model.banks} entries")
        self.write_driver.set({
            "valid": 1, "setIdx": set_index, "waymask": waymask,
            "entries": tuple({"data": e.data, "code": e.code} for e in entries),
        })
        await self.wait_for(lambda: self.write_ready() == 1, what="write ready")
        await self._edge()
        self.write_driver.set({
            "valid": 0, "setIdx": 0, "waymask": 0,
            "entries": tuple({"data": 0, "code": 0} for _ in range(self.model.banks)),
        })
        self.model.write(set_index, waymask, entries)
        await self._edge()

    async def read(self, *requests: ReadRequest) -> tuple[tuple[DataEntry, ...], ...]:
        self.read_driver.set(self._encode_read(tuple(requests)))
        await self.wait_for(lambda: self.read_ready() == 1, what="read ready")
        await self._edge()
        self.read_driver.set(self._encode_read(()))
        expected = self.model.read(tuple(requests))
        values = self.responses()
        for _ in range(self.settle_cycles()):
            await self._edge()
            values = self.responses()
            if values[:len(expected)] == expected:
                break
        return values[:len(expected)]

    async def check_read(self, *requests: ReadRequest):
        expected = self.model.read(tuple(requests))
        actual = await self.read(*requests)
        if actual != expected:
            raise AssertionError(
                f"read: array returned {actual} != model {expected}")
        return actual

    # -- hazard helper ------------------------------------------------------
    def start_write(self, set_index: int, waymask: int) -> None:
        self.write_driver.set({
            "valid": 1, "setIdx": set_index, "waymask": waymask,
            "entries": tuple({"data": 0, "code": 0} for _ in range(self.model.banks)),
        })

    def stop_write(self) -> None:
        self.write_driver.set({
            "valid": 0, "setIdx": 0, "waymask": 0,
            "entries": tuple({"data": 0, "code": 0} for _ in range(self.model.banks)),
        })
