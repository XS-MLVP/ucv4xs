"""Agent for ICacheMissUnit plus the external memory and replacer peers.

The DUT has three missing peers in a unit test:

* the **memory system** on the flattened TileLink acquire/grant channel (it
  accepts one acquire at a time and returns the refill beats with the acquire's
  own source id),
* the **replacer** answering the victim request,
* the **fetch/prefetch pipelines** supplying misses.

``MemoryPeer`` and ``ReplacerPeer`` model those peers from their published
contract only and never read DUT internals.

Timing discipline
-----------------
``xcomm`` commits a level written from Python after one rising edge, and the DUT
samples the committed value on the *next* edge. Two consequences shape this
agent:

* An acquire becomes observable as ``memAcquire.valid`` while it is offered and
  disappears (or is replaced by the next MSHR) on the edge it is accepted. That
  change of the offered source is the acceptance event; a fixed cycle count
  would only encode the harness latency.
* A grant beat written now is sampled two edges later and is held until the level
  is lowered. ``deliver_refill`` therefore writes the payload once, waits for the
  full line, then lowers ``valid`` exactly when the last beat has been sampled.

The reference model is advanced by observed events (allocation, acceptance,
completion, redirect), never by an assumed DUT latency.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace
from typing import Any

from toffee import ClockCycles
from toffee import Execution
from toffee.signals import sample_signal

from suites.frontend.icache.drivers.level import LevelDriver
from suites.frontend.icache.missunit.bundle.ports import MissUnitPorts
from suites.frontend.icache.missunit.model.missunit import MissUnitModel
from suites.frontend.icache.missunit.model.missunit import Response


SETTLE_CYCLES = 40
REFILL_BEATS = 2


@dataclass
class MemoryPeer:
    """TileLink D-channel peer honouring TileLink's corrupt/denied contract."""

    beats: int = REFILL_BEATS
    corrupt: int = 0
    denied: int = 0

    def payload(self, source: int, data: int = 0) -> dict[str, int]:
        # TileLink requires a denied access to also be reported as corrupt.
        return {
            "valid": 1,
            "source": source,
            "data": data,
            "corrupt": int(bool(self.corrupt) or bool(self.denied)),
            "denied": int(bool(self.denied)),
            "opcode": 1,
        }

    def idle(self) -> dict[str, int]:
        return {"valid": 0, "source": 0, "data": 0, "corrupt": 0,
                "denied": 0, "opcode": 0}


@dataclass
class ReplacerPeer:
    """Answers victim requests.  ``way`` is a way *index*, not a one-hot mask."""

    way: int = 0

    def answer(self, vset_idx: int) -> int:  # noqa: ARG002 - set is not needed for a fixed policy
        return self.way & 0b11


@dataclass(frozen=True, slots=True)
class Issue:
    """An MSHR that owns a memory transaction."""

    source: int
    block: int
    vset: int
    way: int


class MissUnitAgent:
    def __init__(self, dut: Any, *, refill_beats: int = REFILL_BEATS) -> None:
        self.dut = dut
        self.ports = MissUnitPorts.bind(dut)
        self.model = MissUnitModel()
        self.memory = MemoryPeer(beats=refill_beats)
        self.replacer = ReplacerPeer()
        self.fetch_driver = LevelDriver(self.ports.fetch_req)
        self.prefetch_driver = LevelDriver(self.ports.prefetch_req)
        self.acquire_driver = LevelDriver(self.ports.acquire_ready)
        self.grant_driver = LevelDriver(self.ports.grant)
        self.victim_driver = LevelDriver(self.ports.victim_way)
        self.fencei_driver = LevelDriver(self.ports.fencei)
        self.flush_driver = LevelDriver(self.ports.flush)
        self.wfi_driver = LevelDriver(self.ports.wfi_req)
        self._execution: Execution | None = None

    # -- lifecycle ----------------------------------------------------------
    async def start(self, execution: Execution) -> "MissUnitAgent":
        self._execution = execution
        self.idle_inputs()
        await self.reset()
        return self

    async def aclose(self) -> None:
        for driver in (self.fetch_driver, self.prefetch_driver, self.acquire_driver,
                       self.grant_driver, self.victim_driver, self.fencei_driver,
                       self.flush_driver, self.wfi_driver):
            driver.close()
        self._execution = None

    def idle_inputs(self) -> None:
        self.fetch_driver.set({"valid": 0, "blkPAddr": 0, "vSetIdx": 0})
        self.prefetch_driver.set({"valid": 0, "blkPAddr": 0, "vSetIdx": 0})
        # The memory peer only takes a request when the test asks it to, so an
        # offered acquire is not silently consumed by the harness.
        self.acquire_driver.set({"ready": 0})
        self.grant_driver.set(self.memory.idle())
        self.victim_driver.set({"way": 0})
        self.fencei_driver.set({"fencei": 0})
        self.flush_driver.set({"flush": 0})
        self.wfi_driver.set({"wfiReq": 0})

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
        self.model = MissUnitModel()
        self.memory = replace(self.memory)
        self.replacer = replace(self.replacer)

    # -- observation --------------------------------------------------------
    @staticmethod
    def _bit(signal: Any) -> int:
        return int(sample_signal(signal).as_int()) & 1

    def _value(self, binding, field: str) -> int:
        return int(sample_signal(binding.bits[field]).as_int())

    def fetch_ready(self) -> int:
        return self._bit(self.ports.fetch_ready.bits["ready"])

    def prefetch_ready(self) -> int:
        return self._bit(self.ports.prefetch_ready.bits["ready"])

    def acquire_valid(self) -> int:
        return self._bit(self.ports.acquire.bits["valid"])

    def acquire_source(self) -> int:
        return self._value(self.ports.acquire, "source")

    def victim_valid(self) -> int:
        return self._bit(self.ports.victim_req.bits["valid"])

    def victim_vset(self) -> int:
        return self._value(self.ports.victim_req, "vSetIdx")

    def resp_valid(self) -> int:
        return self._bit(self.ports.resp.bits["valid"])

    def wfi_safe(self) -> int:
        return self._bit(self.ports.wfi_safe)

    def offer(self) -> int | None:
        """The MSHR the DUT is offering on the memory channel right now."""
        return self.acquire_source() if self.acquire_valid() else None

    async def wait_for(self, predicate, *, what: str, cycles: int = SETTLE_CYCLES) -> None:
        for _ in range(cycles):
            if predicate():
                return
            await self._edge()
        if not predicate():
            raise TimeoutError(
                f"{what} did not happen within {cycles} cycles "
                f"(model entries={self.model.occupied()})")

    async def idle(self, cycles: int = 1) -> None:
        """Advance ``cycles`` with no request activity, keeping the model in step."""
        for _ in range(cycles):
            await self._edge()
            self.model.step()

    # -- allocation ---------------------------------------------------------
    async def _present(self, driver: LevelDriver, payload: dict[str, int],
                       *, model_kwargs: dict[str, int]) -> int:
        """Hold a request on the wire until the DUT has sampled it.

        A level written from Python is committed after one edge and sampled on
        the next, so a request must occupy two edges. The allocation event is
        then recorded on the sampling edge, and the request is withdrawn with
        the same two-edge discipline.
        """
        driver.set(payload)
        await self._edge()
        self.model.step()          # commit edge
        await self._edge()         # sampling edge
        accepted = self.fetch_ready() if driver is self.fetch_driver else self.prefetch_ready()
        self.model.step(**model_kwargs)
        idle = {field: 0 for field in payload}
        driver.set(idle)
        await self._edge()
        self.model.step()
        await self._edge()
        self.model.step()
        return accepted

    async def submit_fetch(self, block: int, vset: int) -> None:
        expected = self.model.fetch_ready() or self.model.hits(block, vset)
        if not expected:
            raise AssertionError(f"fetch pool full (block={block:#x} set={vset:#x})")
        accepted = await self._present(
            self.fetch_driver,
            {"valid": 1, "blkPAddr": block, "vSetIdx": vset},
            model_kwargs={"fetch_valid": 1, "fetch_block": block, "fetch_vset": vset})
        if not accepted:
            raise AssertionError(f"fetch not accepted (block={block:#x})")

    async def submit_prefetch(self, block: int, vset: int) -> None:
        expected = self.model.prefetch_ready() or self.model.hits(block, vset)
        if not expected:
            raise AssertionError(f"prefetch pool full (block={block:#x} set={vset:#x})")
        accepted = await self._present(
            self.prefetch_driver,
            {"valid": 1, "blkPAddr": block, "vSetIdx": vset},
            model_kwargs={"prefetch_valid": 1, "prefetch_block": block,
                          "prefetch_vset": vset})
        if not accepted:
            raise AssertionError(f"prefetch not accepted (block={block:#x})")

    async def submit_same_cycle(self, block: int, vset: int,
                                prefetch_block: int, prefetch_vset: int) -> tuple[int, int]:
        """Present a fetch and a prefetch on the same cycle; returns their readies."""
        self.fetch_driver.set({"valid": 1, "blkPAddr": block, "vSetIdx": vset})
        self.prefetch_driver.set({"valid": 1, "blkPAddr": prefetch_block,
                                  "vSetIdx": prefetch_vset})
        await self._edge()
        self.model.step()
        await self._edge()
        expected_fetch = self.model.fetch_ready() or self.model.hits(block, vset)
        same_cycle = (block == prefetch_block and vset == prefetch_vset)
        expected_prefetch = (self.model.prefetch_ready()
                             or self.model.hits(prefetch_block, prefetch_vset)
                             or same_cycle)
        fetch_ok, prefetch_ok = self.fetch_ready(), self.prefetch_ready()
        if (fetch_ok, prefetch_ok) != (int(bool(expected_fetch)),
                                       int(bool(expected_prefetch))):
            raise AssertionError(
                f"ready mismatch: DUT=({fetch_ok},{prefetch_ok}) "
                f"model=({int(bool(expected_fetch))},{int(bool(expected_prefetch))})")
        self.model.step(fetch_valid=1, fetch_block=block, fetch_vset=vset,
                        prefetch_valid=1, prefetch_block=prefetch_block,
                        prefetch_vset=prefetch_vset)
        self.fetch_driver.set({"valid": 0, "blkPAddr": 0, "vSetIdx": 0})
        self.prefetch_driver.set({"valid": 0, "blkPAddr": 0, "vSetIdx": 0})
        await self._edge()
        self.model.step()
        await self._edge()
        self.model.step()
        return fetch_ok, prefetch_ok

    # -- issue --------------------------------------------------------------
    async def drain(self) -> list[Issue]:
        """Let every allocated MSHR issue and return them in the DUT's order.

        The victim way is supplied as soon as the gate opens, so it is committed
        before the first accepting edge; the way is a single constant for the
        whole drain because back-to-back issues leave no room to rewrite a level
        between two accepting edges.
        """
        if self.model.acquire_select() is None:
            return []
        way = self.replacer.way
        self.victim_driver.set({"way": way})
        self.acquire_driver.set({"ready": 1})

        issues: list[Issue] = []
        previous = self.offer()
        for _ in range(SETTLE_CYCLES):
            victim_valid = self.victim_valid()
            victim_vset = self.victim_vset() if victim_valid else None
            await self._edge()
            current = self.offer()
            accepted = previous is not None and current != previous
            if not accepted:
                self.model.step()
                previous = current
                if current is None and issues:
                    break
                continue
            expected = self.model.acquire_select()
            if expected != previous:
                raise AssertionError(
                    f"DUT issued MSHR {previous} but the model selects {expected}")
            entry = self.model.entries[previous]
            if victim_valid:
                if victim_vset != entry.vset_idx:
                    raise AssertionError(
                        f"victim request set {victim_vset:#x} != MSHR {previous} "
                        f"set {entry.vset_idx:#x}")
            self.model.step(acquire_ready=1, victim_way=way)
            issues.append(Issue(source=previous, block=entry.blk_paddr,
                                vset=entry.vset_idx, way=way))
            previous = current
            if current is None:
                break
        self.acquire_driver.set({"ready": 0})
        for _ in range(2):
            await self._edge()
            self.model.step()
        if self.model.acquire_select() is not None:
            raise AssertionError(
                f"{len(self.model.pending())} allocated MSHR(s) never issued")
        return issues

    # -- refill -------------------------------------------------------------
    async def deliver_refill(self, source: int, *, data: int = 0) -> None:
        """Return a complete line for ``source``.

        A beat written now is sampled two edges later; lowering ``valid`` after
        ``beats`` edges makes the last beat the last one sampled.  ``data`` is
        the 256-bit D-channel payload; random refill data exercises the array
        write path while the observable control response stays model-checked.
        """
        self.grant_driver.set(self.memory.payload(source, data))
        for _ in range(self.memory.beats):
            await self._edge()
            self.model.step()
        # Every beat has been sampled; lowering the level now leaves exactly the
        # last beat on the wire, and the response appears on the edge after it.
        self.grant_driver.set(self.memory.idle())
        await self._edge()
        self.model.step()

    async def complete(self, issue: Issue, *, data: int = 0) -> Response:
        """Refill one MSHR and check the response against the model."""
        await self.deliver_refill(issue.source, data=data)
        expected = self.model.complete(
            issue.source, corrupt=self.memory.corrupt, denied=self.memory.denied)
        if expected.valid:
            await self.wait_for(lambda: self.resp_valid() == 1,
                                what=f"response for MSHR {issue.source}")
            observed = self.sample_response(issue.source)
            if observed != expected:
                raise AssertionError(f"response mismatch:\n  DUT:   {observed}\n"
                                     f"  model: {expected}")
            await self._edge()
            self.model.step()
        else:
            # A redirected refill must complete silently: the entry is freed but
            # nothing may reach the pipeline or the arrays.
            for _ in range(4):
                if self.resp_valid():
                    raise AssertionError(
                        f"MSHR {issue.source} was redirected but still responded")
                await self._edge()
                self.model.step()
            observed = self.sample_response(issue.source)
            if observed.meta_write or observed.data_write:
                raise AssertionError(
                    f"redirected refill wrote the arrays: {observed}")
        return expected

    def sample_response(self, source: int) -> Response:
        return Response(
            source=source,
            valid=self.resp_valid(),
            block=self._value(self.ports.resp, "blkPAddr"),
            vset=self._value(self.ports.resp, "vSetIdx"),
            waymask=self._value(self.ports.resp, "waymask"),
            corrupt=self._bit(self.ports.resp.bits["corrupt"]),
            denied=self._bit(self.ports.resp.bits["denied"]),
            meta_write=self._bit(self.ports.meta_write.bits["valid"]),
            data_write=self._bit(self.ports.data_write.bits["valid"]),
        )

    # -- redirects ----------------------------------------------------------
    async def _pulse(self, driver: LevelDriver, field: str,
                     *, fencei: int = 0, flush: int = 0) -> None:
        """Pulse a redirect level for exactly the edges the DUT samples it."""
        driver.set({field: 1})
        await self._edge()
        self.model.step(fencei=fencei, flush=flush)
        await self._edge()
        self.model.step(fencei=fencei, flush=flush)
        driver.set({field: 0})
        await self._edge()
        self.model.step(fencei=fencei, flush=flush)
        await self._edge()
        self.model.step()

    async def flush(self) -> None:
        await self._pulse(self.flush_driver, "flush", flush=1)

    async def fencei(self) -> None:
        await self._pulse(self.fencei_driver, "fencei", fencei=1)

    async def set_wfi(self, value: int) -> None:
        self.wfi_driver.set({"wfiReq": value})
        await self._edge()
        self.model.step()
        await self._edge()
        self.model.step()

    # -- convenience --------------------------------------------------------
    def occupied(self) -> list[int]:
        return self.model.occupied()
