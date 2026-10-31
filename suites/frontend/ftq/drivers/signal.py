"""Drivers own input pins and the launch/clear timing of their channels.

Every driver claims the pins it writes.  A request is either a one-cycle pulse
with an explicit clear, or a persistent level (ready/control).  Drivers never
read expected values from the DUT.
"""

from __future__ import annotations

from typing import Any
from typing import Mapping

from suites.frontend.ftq.ports import Pins
from suites.frontend.ftq.harness import Dut


class Driver:
    def __init__(self, dut: Dut, pins: Pins) -> None:
        self.dut = dut
        self.pins = pins
        pins.claim(self.name)

    @property
    def name(self) -> str:
        return f"{self.pins.name}.driver"

    def clear(self) -> None:
        for logical in self.pins.names:
            pin = self.pins.names[logical]
            if pin in self.dut._inputs:
                self.dut.input(pin).Set(0)
        self.dut.refresh()

    def close(self) -> None:
        self.clear()


class LevelDriver(Driver):
    """Hold a control level until it is replaced or cleared."""

    async def set(self, values: Mapping[str, int | bool], *, cycles: int = 0) -> None:
        self.pins.set(**values)
        self.dut.refresh()
        if cycles:
            await self.dut.edge(cycles)

    async def clear_after(self, cycles: int = 1) -> None:
        await self.dut.edge(cycles)
        self.clear()


class PulseDriver(Driver):
    """Drive one request cycle, release the touched payload, settle one edge."""

    async def send(self, values: Mapping[str, int | bool], *, hold: int = 1) -> None:
        self.pins.set(**values)
        self.dut.refresh()
        await self.dut.edge(hold)
        for logical in values:
            self.dut.input(self.pins.physical(logical)).Set(0)
        self.dut.refresh()
        await self.dut.edge(1)

    async def send_one_cycle(self, values: Mapping[str, int | bool], *, advance: int = 1) -> None:
        """Drive the request for exactly the given number of edges.

        The caller keeps ownership of the release, which is required when the
        observed head changes on the same edge that admits the request.
        """

        self.pins.set(**values)
        self.dut.refresh()
        await self.dut.edge(advance)

    def release(self, values: Mapping[str, int | bool]) -> None:
        for logical in values:
            self.dut.input(self.pins.physical(logical)).Set(0)
        self.dut.refresh()

    async def send_held(self, values: Mapping[str, int | bool]) -> None:
        """Keep a request asserted across edges until the caller clears it."""

        self.pins.set(**values)
        self.dut.refresh()


class ResetDriver(Driver):
    """Own reset and its release sequence."""

    async def send(self, *, asserted: int = 2, released: int = 2) -> None:
        self.clear()
        self.dut.dut.reset.Set(1)
        await self.dut.edge(asserted)
        self.dut.dut.reset.Set(0)
        await self.dut.edge(released)
        self.dut.refresh()


def claim_all(dut: Dut, owner: str, *groups: Pins) -> None:
    for group in groups:
        group.claim(owner)
