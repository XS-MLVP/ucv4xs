"""Agent for ICacheReplacer.

The adapter has no handshake: a touch beat is applied on every edge its
``valid`` is high, and the victim way is combinational from the requested
``vSetIdx``. The agent therefore drives levels, advances the model exactly once
per edge, and samples the victim output combinationally.

Two conventions come from the module's documented role rather than from the
RTL body: the port/set decomposition of ``vSetIdx`` (low bit selects the fetch
port, remaining bits the set) and the one-cycle victim feedback (the winner of
cycle N is replayed as a touch in cycle N+1 so an immediate refill cannot pick
the same way twice).
"""

from __future__ import annotations

from typing import Any

from toffee import ClockCycles
from toffee import Execution
from toffee.data import compile_sampler

from suites.frontend.icache.drivers.level import LevelDriver
from suites.frontend.icache.replacer.bundle.ports import ReplacerPorts
from suites.frontend.icache.replacer.bundle.ports import touch_binding
from suites.frontend.icache.replacer.bundle.ports import victim_binding
from suites.frontend.icache.replacer.model.plru import ReplacerModel


NUM_SETS = 256
NUM_WAYS = 4
PORTS = 2


class ReplacerAgent:
    def __init__(self, dut: Any, *, sets: int = NUM_SETS, ways: int = NUM_WAYS,
                 ports: int = PORTS) -> None:
        self.dut = dut
        self.ports = ReplacerPorts.bind(dut)
        self.model = ReplacerModel(sets, ways, ports)
        self.touch_drivers = tuple(LevelDriver(touch_binding(dut, port)) for port in range(ports))
        self.victim_driver = LevelDriver(victim_binding(dut))
        self._victim_sampler = compile_sampler(
            self.ports.victim_way if hasattr(self.ports.victim_way, "keys") else self.ports.victim_way)
        self._execution: Execution | None = None

    # -- lifecycle ----------------------------------------------------------
    async def start(self, execution: Execution) -> "ReplacerAgent":
        self._execution = execution
        self._idle_touches()
        self.victim_driver.set({"valid": 0, "vSetIdx": 0})
        await self.reset()
        return self

    async def aclose(self) -> None:
        for driver in self.touch_drivers:
            driver.close()
        self.victim_driver.close()
        self._execution = None

    def _idle_touches(self) -> None:
        for driver, port in zip(self.touch_drivers, self.ports.touch):
            driver.set({"req": tuple(
                {"valid": 0, "vSetIdx": 0, "way": 0} for _ in port.requests)})

    async def reset(self, cycles: int = 3) -> None:
        self.dut.reset.Set(1)
        for _ in range(cycles):
            await ClockCycles(self.dut.clock, 1)
        self.dut.reset.Set(0)
        await ClockCycles(self.dut.clock, 1)
        await ClockCycles(self.dut.clock, 1)
        self.model = ReplacerModel(self.model.num_sets, self.model.num_ways, self.model.ports)

    # -- observation --------------------------------------------------------
    def victim_way(self) -> int:
        value = self.ports.victim_way
        return int(value.U() if hasattr(value, "U") else value)

    def current_victim(self, vset_idx: int) -> int:
        """Ask the DUT for a victim without consuming a cycle.

        The request level is withdrawn immediately: leaving ``valid`` high
        would make the next clock edge latch this victim as a touch, which the
        caller did not ask for.
        """
        self.victim_driver.set({"valid": 1, "vSetIdx": vset_idx})
        way = self.victim_way()
        self.victim_driver.set({"valid": 0, "vSetIdx": 0})
        return way

    async def probe_victim(self, vset_idx: int) -> int:
        """Clock one victim request and check it against the model.

        The victim port has a deliberate side effect: the adapter latches the
        winner and replays it as a touch on the next edge. A combinational read
        therefore cannot observe the policy without altering it, so every check
        goes through a full cycle and the model applies the same feedback.
        """
        expected = self.model.victim(vset_idx)
        observed = await self.request_victim(vset_idx)
        if observed != expected:
            raise AssertionError(
                f"victim({vset_idx:#x}) = {observed} != predicted {expected}")
        return observed

    async def request_victim(self, vset_idx: int) -> int:
        """Present a victim request for one cycle and return the chosen way.

        Unlike :meth:`check_victim` this consumes a clock edge, which is what
        makes the adapter latch the winner and replay it as a touch.
        """
        self.victim_driver.set({"valid": 1, "vSetIdx": vset_idx})
        await ClockCycles(self.dut.clock, 1)
        observed = self.victim_way()
        self.model.step(touches=((), ()), victim_request=vset_idx)
        self.victim_driver.set({"valid": 0, "vSetIdx": 0})
        await ClockCycles(self.dut.clock, 1)
        self.model.step(touches=((), ()), victim_request=None)
        return observed

    def predicted_victim(self, vset_idx: int) -> int:
        return self.model.victim(vset_idx)

    def check_victim(self, vset_idx: int) -> int:
        actual = self.current_victim(vset_idx)
        expected = self.predicted_victim(vset_idx)
        if actual != expected:
            raise AssertionError(
                f"victim({vset_idx:#x}) = {actual} != predicted {expected}")
        return actual

    # -- drive --------------------------------------------------------------
    async def touch_cycle(
        self,
        *,
        port0: tuple[tuple[int, int], ...] = (),
        port1: tuple[tuple[int, int], ...] = (),
        victim_vset: int | None = None,
    ) -> None:
        """Apply one cycle of touches (``(vSetIdx, way)`` per fetch request)."""
        if len(port0) > len(self.ports.touch[0].requests):
            raise ValueError("too many requests on port 0")
        if len(port1) > len(self.ports.touch[1].requests):
            raise ValueError("too many requests on port 1")
        payloads = []
        for driver, entries in zip(self.touch_drivers, (port0, port1)):
            beats = list(entries) + [(0, 0)] * (len(self.ports.touch[0].requests) - len(entries))
            payloads.append({"req": tuple(
                {"valid": 1 if index < len(entries) else 0, "vSetIdx": vs, "way": way}
                for index, (vs, way) in enumerate(beats))})
            driver.set(payloads[-1])
        if victim_vset is None:
            self.victim_driver.set({"valid": 0, "vSetIdx": 0})
        else:
            self.victim_driver.set({"valid": 1, "vSetIdx": victim_vset})

        await ClockCycles(self.dut.clock, 1)
        self.model.step(
            touches=(tuple(port0), tuple(port1)),
            victim_request=victim_vset,
        )
        self._idle_touches()
        self.victim_driver.set({"valid": 0, "vSetIdx": 0})
        await ClockCycles(self.dut.clock, 1)
        # Idle edges still replay a pending victim into the policy.
        self.model.step(touches=((), ()), victim_request=None)

    async def idle_cycle(self) -> None:
        await ClockCycles(self.dut.clock, 1)
        self.model.step(touches=((), ()), victim_request=None)

    # -- scenario helpers ---------------------------------------------------
    def touch(self, vset_idx: int, way: int) -> tuple[int, int]:
        return (vset_idx, way)

    def sequence(self, vset_idx: int, ways: tuple[int, ...]) -> list[tuple[int, int]]:
        """Turn a way sequence into per-request touch tuples for port ``vset&1``."""
        return [(vset_idx, way) for way in ways]

    async def apply_touches(self, vset_idx: int, ways: tuple[int, ...]) -> None:
        """Apply up to two touches per cycle on the port selected by ``vset_idx``."""
        pending = list(ways)
        port = self.model.port_of(vset_idx)
        while pending:
            chunk, pending = pending[:len(self.ports.touch[0].requests)], pending[len(self.ports.touch[0].requests):]
            if port == 0:
                await self.touch_cycle(port0=tuple((vset_idx, way) for way in chunk))
            else:
                await self.touch_cycle(port1=tuple((vset_idx, way) for way in chunk))
