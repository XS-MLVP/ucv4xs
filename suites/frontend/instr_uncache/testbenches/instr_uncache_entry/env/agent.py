"""Cycle agent for InstrUncacheEntry: framework slots, lossless samples, model."""

from __future__ import annotations

from contextlib import asynccontextmanager

from toffee import Execution, XCommClockBackend

from suites.frontend.instr_uncache.testbenches.shared.env.drivers.slot import ExplicitSlotDriver
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import EntryModel
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import Inputs
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import IDLE

from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.checker import check_outputs
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.checker import check_reset
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.env.ports import ABSENT
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.env.ports import INTERFACE
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.env.ports import EntryPorts
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.transactions import CheckedCycle
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.transactions import Events


class EntryAgent:
    def __init__(self, harness):
        self.dut = harness.dut  # Native coverage discovery, never a test API.
        self.interface = INTERFACE
        self._harness = harness
        self._ports = EntryPorts(self.dut)
        self._driver = ExplicitSlotDriver(
            self.dut.clock, self._ports.bits,
            idle=self._ports.encode(Inputs()),
            encoder=self._ports.encode,
            name="instr_uncache.entry.inputs",
        )
        self._monitor = None
        self._model = EntryModel()
        self._used = self._busy = self._finished = self._failed = False
        self._reset_done = False
        self._last_tick = None
        self.checked_cycles = 0

    # -- lifecycle ----------------------------------------------------------
    @asynccontextmanager
    async def running(self):
        if self._used:
            raise RuntimeError("InstrUncacheEntry agent cannot be restarted")
        self._used = True
        from suites.frontend.instr_uncache.testbenches.shared.env.monitors.cycle import DualPhaseMonitor
        monitor = DualPhaseMonitor(self.dut.clock, self._ports.capture, self._ports.capture)
        backend = XCommClockBackend(self.dut.GetXClock())
        try:
            async with Execution(backend) as execution:
                async with self._driver.holding(execution), monitor.running(execution):
                    self._monitor = monitor
                    try:
                        yield self
                        await self.finish()
                    finally:
                        self._monitor = None
        finally:
            backend.close()

    def _enter_work(self):
        if self._monitor is None:
            raise RuntimeError("InstrUncacheEntry requires its fixture-managed Execution")
        if self._finished:
            raise RuntimeError("InstrUncacheEntry input stream is finished")
        if self._failed:
            raise RuntimeError("InstrUncacheEntry has an unreconciled slot after failure")
        if self._busy:
            raise RuntimeError("concurrent InstrUncacheEntry operations are not supported")
        self._busy = True

    async def _exchange(self, inputs: Inputs):
        edge = await self._driver.send(inputs)
        before, after = await self._monitor.recv()
        assert before.event.tick + 1 == edge.tick == after.event.tick, (
            "InstrUncacheEntry stale or missing phase snapshot")
        if self._last_tick is not None:
            assert edge.tick == self._last_tick + 2, (
                "InstrUncacheEntry skipped or repeated an input slot")
        self._last_tick = edge.tick
        return before, after

    async def _cycle_locked(self, inputs: Inputs) -> CheckedCycle:
        if not isinstance(inputs, Inputs):
            raise TypeError("InstrUncacheEntry requires semantic Inputs")
        try:
            expected_before = self._model.outputs(inputs)
            state_before = self._model.state
            # Physical edge happened even if an injected observation fails.
            before, after = await self._exchange(inputs)
            self._model.tick(inputs)
            expected_after = self._model.outputs(inputs)
            state_after = self._model.state
            if inputs.reset:
                check_reset(before.value, phase="before")
                check_reset(after.value, phase="after")
            else:
                check_outputs(expected_before, before.value, phase="before")
                check_outputs(expected_after, after.value, phase="after")
            events = Events(
                req_fire=int(not inputs.reset and before.value.req_ready and inputs.req_valid),
                acquire_fire=int(not inputs.reset and before.value.acquire_valid
                                 and inputs.acquire_ready),
                grant_fire=int(not inputs.reset and inputs.grant_valid),
                resp_fire=int(not inputs.reset and before.value.resp_valid),
            )
            self.checked_cycles += 1
            return CheckedCycle(self.checked_cycles, before.event.tick, after.event.tick,
                                inputs, before.value, after.value, expected_before,
                                expected_after, events, state_before, state_after)
        except BaseException:
            self._failed = True
            raise

    async def reset(self, cycles: int = 3, *, reason: str | None = None) -> None:
        if not isinstance(cycles, int) or cycles < 1:
            raise ValueError("reset requires a positive cycle budget")
        if self._model.outstanding and (not isinstance(reason, str) or not reason.strip()):
            raise ValueError("reset of an outstanding request requires an explicit reason")
        self._enter_work()
        try:
            for _ in range(cycles):
                await self._cycle_locked(Inputs(reset=1))
            self._reset_done = True
            await self._cycle_locked(Inputs())
        except BaseException:
            self._failed = True
            raise
        finally:
            self._busy = False

    # -- public semantic operations ----------------------------------------
    @property
    def state(self) -> str:
        return self._model.state

    @property
    def cycle_count(self) -> int:
        return self.checked_cycles

    def snapshot(self) -> dict[str, object]:
        return self._model.snapshot()

    def audit(self) -> dict:
        return {
            "top": "InstrUncacheEntry",
            "inputs": sorted(INTERFACE["inputs"]),
            "outputs": sorted(INTERFACE["outputs"]),
            "absent": dict(ABSENT),
            "flush": "pruned constant false (Frontend.scala:266)",
            "flush_constant": "false.B",
            "flush_scope": "DefaultConfig/public-a0c2a26cb",
            "flush_behavior": "not behavior-verified: the cancellation path is unreachable",
            "flush_evidence": "docs/spec/verification/evidence/flush-closure.json",
            "response_ready": "pruned constant true (IfuUncacheUnit.scala:133)",
            "grant_ready": "pruned constant true (InstrUncacheImp.scala:88)",
        }

    async def cycle(self, inputs: Inputs = Inputs()) -> CheckedCycle:
        if not self._reset_done:
            raise RuntimeError("InstrUncacheEntry requires an explicit reset before input")
        self._enter_work()
        try:
            return await self._cycle_locked(inputs)
        finally:
            self._busy = False

    async def request(self, addr: int, *, mem_back_mm: int = 1, mem_page_nc: int = 0,
                      acquire_ready: int = 1, wfi_req: int = 0) -> CheckedCycle:
        return await self.cycle(Inputs(req_valid=1, req_addr=addr,
                                       req_mem_back_mm=mem_back_mm,
                                       req_mem_page_nc=mem_page_nc,
                                       acquire_ready=acquire_ready, wfi_req=wfi_req))

    async def acquire(self, *, ready: int = 1, wfi_req: int = 0) -> CheckedCycle:
        return await self.cycle(Inputs(acquire_ready=ready, wfi_req=wfi_req))

    async def grant(self, data: int, *, corrupt: int = 0, denied: int = 0,
                    wfi_req: int = 0) -> CheckedCycle:
        return await self.cycle(Inputs(grant_valid=1, grant_data=data,
                                       grant_corrupt=corrupt, grant_denied=denied,
                                       wfi_req=wfi_req))

    async def idle(self, *, wfi_req: int = 0, acquire_ready: int = 1) -> CheckedCycle:
        return await self.cycle(Inputs(wfi_req=wfi_req, acquire_ready=acquire_ready))

    async def finish(self, max_cycles: int = 2) -> None:
        if self._finished:
            return
        if not isinstance(max_cycles, int) or max_cycles < 1:
            raise ValueError("finish requires a positive cycle budget")
        self._enter_work()
        try:
            if not self._reset_done:
                raise RuntimeError("InstrUncacheEntry requires an explicit reset before finish")
            for _ in range(max_cycles):
                await self._cycle_locked(Inputs())
            assert self._model.state == IDLE, (
                f"InstrUncacheEntry finish has outstanding state {self._model.state}")
            self._model.audit()
            self._finished = True
        except BaseException:
            self._failed = True
            raise
        finally:
            self._busy = False
