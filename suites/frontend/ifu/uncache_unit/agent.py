"""All-channel phase samples, independent protocol checks and bounded UID completion."""
from contextlib import asynccontextmanager
from dataclasses import replace

from toffee import DriveStable, Execution, RisingEdge, SamplingMonitor, XCommClockBackend

from suites.frontend.ifu.drivers.explicit_slots import ExplicitSlotDriver
from suites.frontend.ifu.model.uncache import Inputs, UncacheModel, WAIT_RESP

from .checker import check_outputs, check_reset
from .ledger import RequestLedger
from .ports import UncachePorts
from .types import BusReply, CheckedCycle, CompletedRead, Frame, ReadRequest


class UncacheUnitAgent:
    def __init__(self, harness):
        self.dut = harness.dut  # Native coverage discovery, never a feature-test handle.
        self._ports = UncachePorts(self.dut)
        self._driver = ExplicitSlotDriver(self.dut.clock, self._ports.bits,
            idle=self._ports.encode(Frame()), encoder=self._ports.encode, name='ifu.uncache_unit.inputs')
        self._before = self._after = None
        self._model, self._ledger = UncacheModel(), RequestLedger()
        self._used = self._busy = self._failed = self._finished = self._reset_done = False
        self._last_tick = None
        self.checked_cycles = 0

    @property
    def status(self):
        return self._ledger.snapshot(self._model.phase)

    @property
    def records(self):
        return tuple(self._ledger.records.values())

    @asynccontextmanager
    async def running(self):
        if self._used:
            raise RuntimeError('Uncache agent cannot be restarted')
        self._used = True
        backend = XCommClockBackend(self.dut.GetXClock())
        try:
            async with Execution(backend) as execution:
                before = SamplingMonitor(DriveStable(self.dut.clock), capture=self._ports.capture)
                after = SamplingMonitor(RisingEdge(self.dut.clock), capture=self._ports.capture)
                async with self._driver.holding(execution), before.start(execution), after.start(execution):
                    self._before, self._after = before, after
                    try:
                        yield self
                        await self.finish()
                    finally:
                        self._before = self._after = None
        finally:
            backend.close()

    def _enter_work(self):
        if self._before is None or self._after is None:
            raise RuntimeError('Uncache requires its fixture-managed Execution')
        if self._finished:
            raise RuntimeError('Uncache input stream is finished')
        if self._failed:
            raise RuntimeError('Uncache has an unreconciled input slot after failure/cancellation')
        if self._busy:
            raise RuntimeError('concurrent Uncache operations are not supported')
        self._busy = True

    async def _exchange(self, frame):
        edge = await self._driver.send(frame)
        before, after = await self._before.recv(), await self._after.recv()
        assert before.event.tick + 1 == edge.tick == after.event.tick, 'Uncache stale or missing phase snapshot'
        if self._last_tick is not None:
            assert edge.tick == self._last_tick + 2, 'Uncache skipped or repeated an input slot'
        self._last_tick = edge.tick
        return before, after

    async def reset(self, cycles=3, *, reason=None):
        if not isinstance(cycles, int) or cycles < 1:
            raise ValueError('reset requires a positive cycle budget')
        if self._ledger.active_uid is not None and (not isinstance(reason, str) or not reason.strip()):
            raise ValueError('reset of an outstanding request requires an explicit cancellation reason')
        self._enter_work()
        try:
            for _ in range(cycles):
                _, after = await self._exchange(Frame(reset=1))
                check_reset(after.value)
            self._ledger.reset(after.event.tick, reason or 'initial/idle reset')
            self._model = UncacheModel()
            self._reset_done = True
            await self._cycle(Inputs(to_ready=0), producer=False)
        except BaseException:
            self._failed = True
            raise
        finally:
            self._busy = False

    def _admit(self, inputs, producer, response_uid):
        if not isinstance(inputs, Inputs):
            raise TypeError('Uncache requires semantic Inputs')
        if producer:
            return self._ledger.validate_producer(inputs, self._model.phase, response_uid)
        if response_uid is not None:
            raise ValueError('port characterization has no invented bus response identity')
        return self._ledger.active_uid if inputs.from_valid and self._model.phase == WAIT_RESP else None

    async def _cycle(self, inputs, *, producer, response_uid=None, offer_uid=None, reason='explicit flush cycle'):
        response_uid = self._admit(inputs, producer, response_uid)
        if inputs.req_valid and offer_uid is None:
            offer_uid = self._ledger.offer(ReadRequest(inputs.req_paddr, inputs.req_is_mmio, inputs.req_pbmt),
                                           'producer' if producer else 'port-characterization')
        wanted_before = self._model.outputs(inputs)
        before, after = await self._exchange(Frame(inputs))
        self._model.tick(inputs)  # Physical edge occurred: never rewind shadow state on comparison error.
        wanted_after = self._model.outputs(inputs)
        check_outputs(before.value, wanted_before, phase='before')
        check_outputs(after.value, wanted_after, phase='after')
        events = self._ledger.consume(inputs, before.value, after.value, after.event.tick,
                                      offer_uid, response_uid, reason)
        self.checked_cycles += 1
        return CheckedCycle(self.checked_cycles, before.event.tick, after.event.tick,
                            before.value, after.value, events, self.status)

    async def _submit(self, inputs, *, producer, response_uid=None, reason='explicit flush cycle'):
        self._admit(inputs, producer, response_uid)  # Reject before entering a clocked slot.
        self._enter_work()
        try:
            if not self._reset_done:
                raise RuntimeError('Uncache requires an explicit reset before input')
            return await self._cycle(inputs, producer=producer, response_uid=response_uid, reason=reason)
        except BaseException:
            self._failed = True
            raise
        finally:
            self._busy = False

    async def cycle(self, inputs=Inputs(to_ready=0), *, response_uid=None):
        return await self._submit(inputs, producer=True, response_uid=response_uid)

    async def characterize_cycle(self, inputs):
        """Explicit leaf-port pressure: all checks remain, no producer provenance credit."""
        return await self._submit(inputs, producer=False)

    async def reply(self, uid, response):
        if not isinstance(response, BusReply):
            raise TypeError('Uncache reply requires a semantic BusReply')
        inputs = Inputs(to_ready=0, from_valid=1, from_data=response.data,
            from_corrupt=response.corrupt, from_denied=response.denied, from_need_resend=response.need_resend)
        return await self._submit(inputs, producer=True, response_uid=uid)

    async def cancel_pending(self, reason):
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError('cancellation requires an explicit reason')
        return await self._submit(Inputs(flush=1, to_ready=0), producer=False, reason=reason)

    async def read(self, request, response, *, max_cycles=12):
        """An explicit caller-owned peer supplies this reply only after observed bus issue."""
        if not isinstance(request, ReadRequest) or not isinstance(response, BusReply):
            raise TypeError('Uncache read requires ReadRequest and BusReply')
        if not isinstance(max_cycles, int) or max_cycles < 1:
            raise ValueError('read requires a positive cycle budget')
        first = Inputs(req_valid=1, req_paddr=request.paddr, req_is_mmio=request.is_mmio,
                       req_pbmt=request.pbmt, is_first_instr=1, empty_after=1)
        self._admit(first, True, None)
        if response.need_resend != self._ledger.expected_resend(request, response.data, response.corrupt):
            raise ValueError('InstrUncache producer needResend must match clean nonRVC cross-page data')
        if self._ledger.active_uid is not None:
            raise RuntimeError('complete or explicitly cancel the current read first')
        self._enter_work()
        try:
            if not self._reset_done:
                raise RuntimeError('Uncache requires an explicit reset before input')
            uid = self._ledger.offer(request, 'producer')
            accepted = issued = False
            for _ in range(max_cycles):
                inputs = Inputs(is_first_instr=1, empty_after=1)
                if not accepted:
                    inputs = first
                elif issued:
                    inputs = replace(inputs, from_valid=1, from_data=response.data,
                        from_corrupt=response.corrupt, from_denied=response.denied,
                        from_need_resend=response.need_resend)
                checked = await self._cycle(inputs, producer=True,
                    response_uid=uid if issued else None, offer_uid=uid)
                accepted |= checked.events.accepted_uid == uid
                issued |= checked.events.bus_fire_uid == uid
                if checked.events.completed_uid == uid:
                    return CompletedRead(uid, response, checked)
            raise AssertionError(f'Uncache read UID{uid} did not complete within {max_cycles} cycles; '
                                 f'accepted={accepted}, issued={issued}')
        except BaseException:
            self._failed = True
            raise
        finally:
            self._busy = False

    async def finish(self, max_cycles=2):
        if self._finished:
            return
        if not isinstance(max_cycles, int) or max_cycles < 1:
            raise ValueError('finish requires a positive cycle budget')
        self._enter_work()
        try:
            if not self._reset_done:
                raise RuntimeError('Uncache requires an explicit reset before finish')
            for _ in range(max_cycles):
                await self._cycle(Inputs(to_ready=0), producer=False)
            assert self._ledger.active_uid is None, 'Uncache finish has an outstanding request; no automatic reply/flush/reset'
            assert self._ledger.pulse_uid is None, 'Uncache completion pulse did not clear'
            self._ledger.audit()
            self._finished = True
        except BaseException:
            self._failed = True
            raise
        finally:
            self._busy = False
