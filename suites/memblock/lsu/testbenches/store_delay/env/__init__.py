"""Environment and independent reference for DelayPipeline (store S3 writeback).

The model keeps ``(reg_valid, reg_bits)`` and applies, once per clock:

    prevFire   = in.valid and not needFlush(in.robIdx)
    next_valid = prevFire
    next_bits  = in.bits if prevFire else reg_bits

``next_valid = prevFire`` is not a simplification: ``io_out_ready`` is tied
high in the parent and was constant-propagated away (the generated DUT has no
ready port), so a registered beat is consumed in the very cycle it appears and
never persists. The RTL's additional ``curKill`` term on the registered beat is
therefore unobservable at this boundary; ``OutputKillProbe`` below measures
that equivalence instead of pretending to check it.

The ``needFlush`` predicate is written from the RobPtr relation, not from the
RTL bit expression.

Contract: docs/spec/design/contracts/store-delay.md. Driver/Monitor lifetime and the final
registered beat are checked by running(); no testcase advances the native DUT.
"""
from __future__ import annotations

import random
from contextlib import asynccontextmanager

from toffee import DriveStable, Execution, SamplingMonitor, SyncSingleCycleDriver, XCommClockBackend

from suites.memblock.lsu.testbenches.store_delay.env.ports import DelayPorts
from suites.memblock.lsu.testbenches.store_delay.transactions import DelayCommand
from suites.memblock.lsu.testbenches.store_delay.transactions import PAYLOAD_FIELDS

from suites.memblock.lsu.testbenches.new_store_unit.transactions import LEVEL_FLUSH
from suites.memblock.lsu.testbenches.new_store_unit.transactions import LEVEL_FLUSH_AFTER
from suites.memblock.lsu.testbenches.new_store_unit.transactions import is_after_slot
from suites.memblock.lsu.testbenches.new_store_unit.transactions import is_same_entry
from suites.memblock.lsu.testbenches.new_store_unit.transactions import is_same_slot
from suites.memblock.lsu.testbenches.new_store_unit.transactions import rob_need_flush as need_flush

class DelayReference:
    def __init__(self) -> None:
        self.valid = 0
        self.bits = {name: 0 for name in PAYLOAD_FIELDS}

    def push(self, in_valid: int, in_bits: dict[str, int], redirect: dict) -> None:
        prev_fire = bool(in_valid) and not need_flush(
            in_bits["uop_robIdx_flag"], in_bits["uop_robIdx_value"],
            in_bits["uop_robIdx_isFormer"], redirect)
        if prev_fire:
            self.bits = {name: in_bits[name] for name in PAYLOAD_FIELDS}
        self.valid = 1 if prev_fire else 0

    def snapshot(self) -> dict:
        return dict(valid=self.valid, bits=dict(self.bits))


def make_bits(rng: random.Random | None = None, **overrides) -> dict[str, int]:
    bits = {}
    for name, width in PAYLOAD_FIELDS.items():
        limit = 160 if name == 'uop_robIdx_value' else 1 << width
        bits[name] = rng.randrange(limit) if rng is not None else 0
    if overrides.keys() - PAYLOAD_FIELDS.keys():
        raise ValueError('unknown StoreDelay payload fields: ' + repr(sorted(overrides.keys() - PAYLOAD_FIELDS.keys())))
    bits.update(overrides)
    return bits


class StoreDelayEnv:
    def __init__(self, dut, coverage=None) -> None:
        self.dut = dut
        self.coverage = coverage
        self._ports = DelayPorts(dut)
        self._idle = DelayCommand.build(0, {name: 0 for name in PAYLOAD_FIELDS}, no_redirect())
        self._driver = SyncSingleCycleDriver(dut.clock, self._ports.bits,
            idle=self._ports.encode(self._idle), encoder=self._ports.encode, name='store_delay.inputs')
        self._monitor = None
        self._output = None
        self._busy = False
        self.model = DelayReference()
        self.cycles = 0

    # ------------------------------------------------------------------ reset
    @asynccontextmanager
    async def running(self):
        if self._monitor is not None:
            raise RuntimeError('StoreDelay environment already running')
        backend = XCommClockBackend(self.dut.GetXClock())
        try:
            async with Execution(backend) as execution:
                monitor = SamplingMonitor(DriveStable(self.dut.clock), capture=self._ports.capture)
                async with self._driver, monitor.start(execution):
                    self._monitor = monitor
                    try:
                        yield self
                        await self.finish()
                    finally:
                        self._monitor = None
        finally:
            backend.close()

    async def _exchange(self, command):
        if self._monitor is None:
            raise RuntimeError('StoreDelay transactions require running()')
        if self._busy:
            raise RuntimeError('concurrent StoreDelay cycle calls are not supported')
        self._busy = True
        try:
            edge = await self._driver.send(command)
            transfer = await self._monitor.recv()
            assert transfer.event.tick + 1 == edge.tick, 'stale StoreDelay observation'
            self._output = transfer.value
            return transfer.value
        finally:
            self._busy = False

    async def reset(self, cycles: int = 4) -> None:
        if cycles < 1:
            raise ValueError('reset requires a positive cycle count')
        command = DelayCommand.build(0, {name: 0 for name in PAYLOAD_FIELDS}, no_redirect(), reset=True)
        for _ in range(cycles):
            await self._exchange(command)
        self.model = DelayReference()
        await self.cycle(0, {name: 0 for name in PAYLOAD_FIELDS}, no_redirect(), 'after reset')

    def observation(self):
        if self._output is None:
            raise RuntimeError('StoreDelay has no sampled output')
        return self._output

    async def finish(self):
        # Check the final registered beat, then a no-repeat control. Calling a
        # driver once is not proof that its final output was ever compared.
        zero = {name: 0 for name in PAYLOAD_FIELDS}
        await self.cycle(0, zero, no_redirect(), 'finish pending beat')
        await self.cycle(0, zero, no_redirect(), 'finish no duplicate')

    # -------------------------------------------------------------- one cycle
    async def cycle(self, in_valid: int, in_bits: dict[str, int], redirect: dict,
              context: str = "cycle") -> dict:
        """Sample the outputs of the current cycle, then apply this cycle's inputs.

        The returned dict is the state *before* this cycle's clock edge, so a
        beat driven at T is returned by the call for T+1: the DUT latency is one
        cycle both in the model and in the returned data.
        """
        want = self.model.snapshot()
        command = DelayCommand.build(in_valid, in_bits, redirect)
        got = (await self._exchange(command)).mapping()
        got_valid, got_bits = got['valid'], got['bits']
        if got_valid != want["valid"]:
            raise AssertionError(
                f"{context}: out.valid {got_valid} != {want['valid']} "
                f"(redirect={redirect})")
        # Payload is only meaningful while out.valid is high; the register keeps
        # stale bytes when the beat has been consumed, and the contract declares
        # that don't-care explicitly.
        if want["valid"]:
            for name, got in got_bits.items():
                if got != want["bits"][name]:
                    raise AssertionError(
                        f"{context}: out.{name} {got:#x} != {want['bits'][name]:#x}")
        self.coverage and self.coverage.observe(
            out_valid=got_valid, in_valid=int(in_valid), redirect=redirect,
            in_bits=in_bits, out_bits=got_bits)
        self.model.push(in_valid, in_bits, redirect)
        self.cycles += 1
        return {"valid": got_valid, "bits": got_bits}


def no_redirect() -> dict:
    return {"valid": 0, "level": 0, "flag": 0, "value": 0, "former": 0}


def redirect(flag=0, value=0, former=1, level=LEVEL_FLUSH, valid=1) -> dict:
    return {"valid": valid, "level": level, "flag": flag, "value": value,
            "former": former}
