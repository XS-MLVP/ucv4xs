"""Agent for ICacheMshr plus an external miss-unit helper.

Why this agent waits instead of counting cycles
-----------------------------------------------
A level written with ``Set`` reaches the DUT one rising edge later
(``xcomm`` commits writes on the rising phase), and a level that *changes*
still participates in the commit edge with its previous value. The observable
input-to-effect latency is therefore one or two edges depending on whether the
stimulus changed, so asserting a fixed cycle count would encode the harness's
own latency into the expectations.

Instead the agent drives level signals and waits for the expected observable
transition with a bounded retry count. The reference model is advanced by the
*observed event* (allocated, issued, completed, flushed) and then supplies the
architecture-level consequences - secondary-hit identity, ready gating, bypass
publication, WFI safety - which are what the assertions compare.

The external ``MissUnitHelper`` plays the missing peer: it accepts the acquire,
supplies the replacement way, and signals completion after a drain delay. It
only consumes the DUT's published ports, never its internals.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from toffee import ClockCycles
from toffee import Execution
from toffee.signals import sample_signal

from icacheverify.common.driver.level import LevelDriver
from icacheverify.mshr.bundle.ports import MshrPorts
from icacheverify.mshr.model.mshr import MshrModel


SETTLE_CYCLES = 8


@dataclass
class MissUnitHelper:
    """Event-driven peer that services the MSHR's acquire channel."""

    victim_way: int = 0
    drain_cycles: int = 3

    def way_for(self, cycle: int = 0) -> int:
        """Replacement way the miss unit would supply for the next fetch."""
        return (self.victim_way + cycle) & 0b11


class MshrAgent:
    def __init__(self, dut: Any) -> None:
        self.dut = dut
        self.ports = MshrPorts.bind(dut)
        self.model = MshrModel()
        self.helper = MissUnitHelper()
        self.request_driver = LevelDriver(self.ports.request)
        self.lookup_drivers = tuple(LevelDriver(port) for port in self.ports.lookup)
        self.acquire_driver = LevelDriver(self.ports.acquire_ready)
        self.fencei_driver = LevelDriver(self.ports.fencei)
        self.invalid_driver = LevelDriver(self.ports.invalid)
        self.victim_driver = LevelDriver(self.ports.victim_way)
        self.wfi_driver = LevelDriver(self.ports.wfi)
        self._execution: Execution | None = None
        self.edges = 0

    # -- lifecycle ----------------------------------------------------------
    async def start(self, execution: Execution) -> "MshrAgent":
        self._execution = execution
        self.idle_inputs()
        await self.reset()
        return self

    async def aclose(self) -> None:
        for driver in (self.request_driver, *self.lookup_drivers, self.acquire_driver,
                       self.fencei_driver, self.invalid_driver, self.victim_driver,
                       self.wfi_driver):
            driver.close()
        self._execution = None

    def idle_inputs(self) -> None:
        """Everything deasserted: a true no-op cycle for the model."""
        self.request_driver.set({"valid": 0, "blkPAddr": 0, "vSetIdx": 0})
        for driver in self.lookup_drivers:
            driver.set({"blkPAddr": 0, "vSetIdx": 0})
        self.acquire_driver.set({"ready": 0})
        self.fencei_driver.set({"fencei": 0})
        self.invalid_driver.set({"invalid": 0})
        self.victim_driver.set({"victimWay": 0})
        self.wfi_driver.set({"wfiReq": 0})

    async def reset(self, cycles: int = 3) -> None:
        self.idle_inputs()
        self.dut.reset.Set(1)
        for _ in range(cycles):
            await self._edge()
        self.dut.reset.Set(0)
        await self._edge()
        await self._edge()
        self.model = MshrModel()
        self.edges = 0

    async def _edge(self) -> None:
        await ClockCycles(self.dut.clock, 1)
        self.edges += 1

    # -- observation --------------------------------------------------------
    @staticmethod
    def _bit(signal: Any) -> int:
        return int(sample_signal(signal).as_int()) & 1

    def req_ready(self) -> int:
        return self._bit(self.ports.ready)

    def acquire_valid(self) -> int:
        return self._bit(self.ports.acquire.bits["valid"])

    def info_valid(self) -> int:
        return self._bit(self.ports.info.bits["valid"])

    def wfi_safe(self) -> int:
        return self._bit(self.ports.wfi_safe)

    def hits(self) -> tuple[int, ...]:
        return tuple(self._bit(signal) for signal in self.ports.hit)

    def info_way(self) -> int:
        return int(sample_signal(self.ports.info.bits["way"]).as_int()) & 0b11

    def info_block(self) -> int:
        return int(sample_signal(self.ports.info.bits["blkPAddr"]).as_int())

    async def wait_for(self, predicate, *, what: str, cycles: int = SETTLE_CYCLES) -> None:
        for _ in range(cycles):
            if predicate():
                return
            await self._edge()
        if not predicate():
            raise TimeoutError(f"{what} did not happen within {cycles} edges "
                               f"(state={self.model.state})")

    # -- architecture-level operations --------------------------------------
    async def allocate(self, block: int, vset: int) -> None:
        """Present a miss request until the entry reports it is live."""
        assert self.model.state.valid == 0, "allocate() needs a free MSHR"
        self.request_driver.set({"valid": 1, "blkPAddr": block, "vSetIdx": vset})
        # ``info.valid`` rising is the unambiguous allocation event.
        await self.wait_for(lambda: self.info_valid() == 1, what="MSHR allocation")
        self.model.step(req_valid=1, req_block=block, req_vset=vset, acquire_ready=0)
        self.request_driver.set({"valid": 0, "blkPAddr": 0, "vSetIdx": 0})
        if self.model.state.blk_paddr != block or self.model.state.vset_idx != vset:
            raise AssertionError("the model did not record the allocated block")
        if self.info_block() != block:
            raise AssertionError(f"info.blkPAddr {self.info_block():#x} != {block:#x}")

    async def issue(self, victim_way: int) -> None:
        """Let the miss unit accept the acquire and confirm the way capture."""
        self.victim_driver.set({"victimWay": victim_way})
        self.acquire_driver.set({"ready": 1})
        # First the fetch must actually be offered, then it must stop being
        # offered - that falling edge is the acceptance event. Waiting only for
        # the fall would accept immediately when the acquire was being held.
        await self.wait_for(lambda: self.acquire_valid() == 1,
                            what="acquire to be offered")
        await self.wait_for(lambda: self.acquire_valid() == 0, what="acquire acceptance")
        self.model.step(acquire_ready=1, victim_way=victim_way)
        self.acquire_driver.set({"ready": 0})
        if self.model.state.way != victim_way:
            raise AssertionError("model did not capture the victim way")
        # The way is a register written on the accepting edge, so it appears in
        # the published information one edge later.
        await self.wait_for(lambda: self.info_way() == victim_way,
                            what=f"captured way {victim_way} to be published")

    async def complete(self) -> None:
        """Signal completion the way the miss unit does, then free the entry."""
        self.invalid_driver.set({"invalid": 1})
        await self.wait_for(
            lambda: self.info_valid() == 0 and self.req_ready() == 1,
            what="entry release after completion")
        self.model.step(invalid=1)
        self.invalid_driver.set({"invalid": 0})

    async def flush(self) -> None:
        """Assert fence.i and wait for the entry to stop publishing."""
        self.fencei_driver.set({"fencei": 1})
        await self.wait_for(lambda: self.info_valid() == 0,
                         what="bypass publication to stop after fence.i")
        self.model.step(fencei=1)
        self.fencei_driver.set({"fencei": 0})

    async def check_hits(self, *pairs: tuple[int, int]) -> tuple[int, ...]:
        """Secondary lookup; the driven addresses need one edge to commit."""
        for index, driver in enumerate(self.lookup_drivers):
            block, vset = pairs[index] if index < len(pairs) else (0, 0)
            driver.set({"blkPAddr": block, "vSetIdx": vset})
        await self._edge()
        actual = self.hits()
        expected = tuple(
            self.model.hit(block, vset)
            for block, vset in pairs + ((0, 0),) * (len(self.lookup_drivers) - len(pairs)))
        if actual != expected:
            raise AssertionError(
                f"lookup hits {actual} != model {expected} (state={self.model.state})")
        return actual
