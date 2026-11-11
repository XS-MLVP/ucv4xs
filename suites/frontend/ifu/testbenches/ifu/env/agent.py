"""Continuous phase/UID checking of cached and caller-owned uncached histories.

Pipeline history associates identities; instruction answers remain independent
byte-stream/ISA oracles. The uncached protocol composes the already tested child
reference model, never internal DUT signals or data-derived response identities.
"""
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace

from toffee import DriveStable, Execution, RisingEdge, SamplingMonitor, Scoreboard, XCommClockBackend

from suites.frontend.ifu.testbenches.shared.env.driver.explicit_slots import ExplicitSlotDriver
from suites.frontend.ifu.testbenches.frontend_trigger.checker import require_csr_table
from suites.frontend.ifu.testbenches.perf_analysis.model.perf import PerfModel
from suites.frontend.ifu.testbenches.ifu.model.fetch_events import NAMES as EVENT_NAMES
from suites.frontend.ifu.testbenches.ifu.model.fetch_events import event_counts
from suites.frontend.ifu.testbenches.frontend_trigger.model.trigger import TriggerModel
from suites.frontend.ifu.testbenches.uncache_unit.model.uncache import Inputs as UncacheInputs
from suites.frontend.ifu.testbenches.uncache_unit.model.uncache import Outputs as UncacheOutputs
from suites.frontend.ifu.testbenches.uncache_unit.model.uncache import UncacheModel
from suites.frontend.ifu.testbenches.uncache_unit.model.uncache import WAIT_RESP
from suites.frontend.ifu.testbenches.uncache_unit.env.ledger import RequestLedger
from suites.frontend.ifu.testbenches.uncache_unit.transactions import BusReply
from suites.frontend.ifu.testbenches.uncache_unit.transactions import ReadRequest

from suites.frontend.ifu.testbenches.ifu.checker import cached_expectation
from suites.frontend.ifu.testbenches.ifu.checker import check_enqueue
from suites.frontend.ifu.testbenches.ifu.checker import check_gpa
from suites.frontend.ifu.testbenches.ifu.checker import check_uncached_enqueue
from suites.frontend.ifu.testbenches.ifu.checker import expected_redirect
from suites.frontend.ifu.testbenches.ifu.checker import uncached_redirect
from suites.frontend.ifu.testbenches.ifu.env.ports import IfuPorts
from suites.frontend.ifu.testbenches.ifu.transactions import BusRequest
from suites.frontend.ifu.testbenches.ifu.transactions import CheckedCycle
from suites.frontend.ifu.testbenches.ifu.transactions import FetchRequest
from suites.frontend.ifu.testbenches.ifu.transactions import FetchResult
from suites.frontend.ifu.testbenches.ifu.transactions import Frame
from suites.frontend.ifu.testbenches.ifu.transactions import ProducerFetchRequest
from suites.frontend.ifu.testbenches.ifu.transactions import Redirect
from suites.frontend.ifu.testbenches.ifu.transactions import Snapshot


@dataclass(frozen=True)
class HalfInstruction:
    pc: int
    low: int
    uid: int
    peer_source: str = 'producer'
    input_source: str = 'port-characterization'


@dataclass(frozen=True)
class CarryCancellation:
    half: HalfInstruction
    reason: str
    operation: str
    tick: int


@dataclass(frozen=True)
class FetchRecord:
    uid: int
    epoch: int
    request: FetchRequest
    accepted_tick: int | None
    effective: FetchRequest | None = None
    pointer: int = 0
    state: str = 'pending'
    beat: object = None
    redirect: object = None
    gpa: object = None
    beat_tick: int | None = None
    redirect_tick: int | None = None
    cancel_reason: str | None = None
    carry_in: HalfInstruction | None = None
    unit_accepted_tick: int | None = None
    issued_tick: int | None = None
    bus: BusRequest | None = None
    reply_tick: int | None = None
    reply: BusReply | None = None
    reply_source: str | None = None
    completion_source: str | None = None
    cache_hits: tuple[int, int] = (0, 0)
    double_line: int = 0

    @property
    def shift(self):
        return self.pointer & 3

    @property
    def input_source(self):
        if self.carry_in is not None and self.carry_in.input_source != 'producer':
            return 'port-characterization'
        return self.request.input_source


@dataclass(frozen=True)
class CycleContract:
    redirect: Redirect | None
    redirect_uid: int | None
    wb_redirect: bool
    s2_flush: bool
    frontend_flush: bool
    bpu: bool
    s1_moves: bool
    fetch_ready: bool
    uncache: bool
    resend: bool
    uncache_redirect: bool
    unit_inputs: UncacheInputs
    unit_outputs: UncacheOutputs


class IfuAgent:
    def __init__(self, harness):
        self.dut = harness.dut  # Coverage/resource boundary only.
        self._ports = IfuPorts(self.dut)
        self._driver = ExplicitSlotDriver(self.dut.clock, self._ports.bits,
            idle=self._ports.encode(Frame()), encoder=self._ports.encode, name='ifu.top.inputs')
        self._before = self._after = None
        self._used = self._busy = self._failed = self._finished = self._reset_done = False
        self._last_tick = None
        self._sequence = self._epoch = self._pointer = self._uid = 0
        self._records = {}
        self._s1 = self._s2 = self._wb = self._half = None
        self._s2_new = False
        self._trigger, self._perf = TriggerModel(), PerfModel()
        self._unit = UncacheModel()
        self._unit_owner = None
        self._uncache_busy = False
        self._first_instruction = True
        self._seen_replies = set()
        self._event_pipe = (None, None)  # Reset-less public two-register interface.
        self._carry_cancellations = []
        self.req_fires = self.cancelled_on_fire = self.beat_fires = self.redirects = self.gpa_writes = 0
        self.offered_cycles = 0
        self.bus_fires = self.flushed_bus_fires = self.reply_fires = self.ignored_replies = 0

    @property
    def records(self):
        return tuple(self._records.values())

    @property
    def interface(self):
        return self._ports.interface

    @property
    def outstanding(self):
        return tuple(record.uid for record in self.records if record.state == 'pending')

    @property
    def carry(self):
        return self._half

    @property
    def carry_cancellations(self):
        return tuple(self._carry_cancellations)

    @property
    def checked_cycles(self):
        return self._sequence

    @property
    def uncache_phase(self):
        return self._unit.phase  # Independent protocol history, not a DUT peek.

    @asynccontextmanager
    async def running(self):
        if self._used:
            raise RuntimeError('IFU agent cannot be restarted')
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

    def _enter(self):
        if self._before is None or self._after is None:
            raise RuntimeError('IFU requires its fixture-managed Execution')
        if self._finished:
            raise RuntimeError('IFU stream is finished')
        if self._failed:
            raise RuntimeError('IFU has an unreconciled sampled slot after failure/cancellation')
        if self._busy:
            raise RuntimeError('concurrent IFU operations are not supported')
        self._busy = True

    async def _exchange(self, frame):
        completed = await self._driver.send(frame)
        before, after = await self._before.recv(), await self._after.recv()
        assert before.event.tick + 1 == completed.tick == after.event.tick, 'IFU stale or missing phase snapshot'
        if self._last_tick is not None:
            assert completed.tick == self._last_tick + 2, 'IFU skipped or repeated an input slot'
        if not isinstance(before.value, Snapshot) or not isinstance(after.value, Snapshot):
            raise TypeError('IFU requires complete immutable phase snapshots')
        self._last_tick = completed.tick
        return before, after

    async def reset(self, cycles=3, *, reason=None):
        if type(cycles) is not int or cycles < 1:
            raise ValueError('reset requires a positive cycle budget')
        if (self.outstanding or self._half is not None) and (not isinstance(reason, str) or not reason.strip()):
            raise ValueError('reset of outstanding fetch/carry requires an explicit reason')
        self._enter()
        try:
            for _ in range(cycles):
                # Reset clears the visible pipeline before this sampling slot;
                # a pre-reset held UID is not a new IBuffer fire. The reset-less
                # event registers still advance, preserving known older events.
                pulse = (0,) * 13
                before, after = await self._exchange(Frame(reset=1))
                self._check_events(before.value, 'reset-before')
                self._event_pipe = (self._event_pipe[1], pulse)
                self._check_events(after.value, 'reset-after')
                assert after.value.fetch_ready == 1 and after.value.beat is None and after.value.redirect is None \
                    and after.value.bus is None and after.value.gpa is None and after.value.reasons == 0, 'IFU reset left a live output'
            for uid in self.outstanding:
                self._records[uid] = replace(self._records[uid], state='cancelled', cancel_reason=reason)
            if self._half is not None:
                self._carry_cancellations.append(CarryCancellation(self._half, reason, 'reset', self._last_tick))
            self._pointer = 0
            self._s1 = self._s2 = self._wb = self._half = None
            self._s2_new = False
            self._trigger, self._perf = TriggerModel(), PerfModel()
            self._unit = UncacheModel()
            self._unit_owner = None
            self._uncache_busy = False
            self._first_instruction = True
            self._epoch += 1
            self._reset_done = True
            await self._cycle(Frame())
        except BaseException:
            self._failed = True
            raise
        finally:
            self._busy = False

    @staticmethod
    def _uncached(request):
        w = request.window
        return not w.exc0 and bool(w.pmp0 or w.pbmt0 in (1, 2))

    @staticmethod
    def _effective(record, frame):
        w = record.request.window
        return replace(record.request, window=replace(w,
            exc0=w.exc0 or (5 if any(frame.corruption[:2]) else 0),
            exc1=w.exc1 or (5 if any(frame.corruption[2:]) else 0)))

    def _control(self, frame):
        wb = self._records[self._wb] if self._wb is not None else None
        cache_redirect = expected_redirect(wb.effective, wb.shift) if wb is not None else None
        s2 = self._records[self._s2] if self._s2 is not None else None
        # A prediction redirect must not cancel its own held IBuffer beat.
        s2_flush = bool(frame.backend_redirect or (cache_redirect is not None and (
            s2 is None or wb.request.window.ftq0 != s2.request.window.ftq0)))
        uncache = s2 is not None and self._uncached(s2.effective)
        w = s2.effective.window if s2 is not None else None
        reply = frame.reply
        inputs = UncacheInputs(flush=int(s2_flush), req_valid=int(uncache and not self._uncache_busy),
            req_paddr=s2.request.physical_address if s2 is not None else 0,
            req_is_mmio=w.pmp0 if w is not None else 0, req_pbmt=w.pbmt0 if w is not None else 0,
            is_first_instr=int(self._first_instruction), ifu_stall=1 - frame.ibuffer_ready,
            empty_after=frame.backend_empty & frame.ibuffer_empty, to_ready=frame.uncache_ready,
            from_valid=int(reply is not None), from_data=reply.data if reply else 0,
            from_corrupt=reply.corrupt if reply else 0, from_denied=reply.denied if reply else 0,
            from_need_resend=reply.need_resend if reply else 0)
        response = self._unit.outputs(inputs)
        resend = bool(uncache and response.resp_valid and response.resp_need_resend)
        can_go = not uncache or bool(response.resp_valid and not response.resp_need_resend)
        unc_redirect = bool(uncache and frame.ibuffer_ready and (can_go or resend))
        redirect = cache_redirect
        redirect_uid = self._wb if cache_redirect is not None else None
        if wb is None and unc_redirect and not frame.backend_redirect:
            redirect = uncached_redirect(s2.effective, response, s2.carry_in)
            redirect_uid = s2.uid
        frontend_flush = bool(frame.backend_redirect or cache_redirect is not None or unc_redirect)
        bpu = False
        if frame.request is not None and frame.bpu_flush is not None:
            flag, value = frame.bpu_flush
            other_flag, other_value = frame.request.window.ftq0
            after = (value > other_value) if flag == other_flag else (value < other_value)
            bpu = not after
        s2_ready = self._s2 is None or bool(frame.ibuffer_ready and can_go)
        s1_moves = self._s1 is not None and s2_ready
        fetch_ready = bool(self._s1 is None or s1_moves or frontend_flush or bpu)
        return CycleContract(redirect, redirect_uid, cache_redirect is not None, s2_flush, frontend_flush,
            bpu, s1_moves, fetch_ready, uncache, resend, unc_redirect, inputs, response)

    def _check_phase(self, frame, sample, *, phase):
        contract = self._control(frame)
        self._check_events(sample, phase)
        assert sample.fetch_ready == contract.fetch_ready, f'ifu.top.{phase}: wrong fetch_ready'
        assert (sample.redirect is not None) == (contract.redirect is not None), f'ifu.top.{phase}: missing or repeated redirect'
        if contract.redirect is not None:
            Scoreboard('ifu.top.redirect').check(expected=contract.redirect, actual=sample.redirect)
        response = contract.unit_outputs
        bus = BusRequest(response.to_paddr, response.to_mem_back_mm, response.to_mem_page_nc) if response.to_valid else None
        Scoreboard(f'ifu.top.{phase}.bus').check(expected=bus, actual=sample.bus)
        has_beat = self._s2 is not None and not contract.s2_flush and (
            not contract.uncache or bool(response.resp_valid and not response.resp_need_resend))
        assert (sample.beat is not None) == has_beat, f'ifu.top.{phase}: missing or repeated enqueue'
        if has_beat:
            record = self._records[self._s2]
            expected = cached_expectation(record.effective, record.shift, fs_is_off=frame.fs_is_off)[0]
            pcs = list(expected.pcs)
            if record.carry_in is not None:
                pcs[record.shift] = record.carry_in.pc
            trigger_actions = self._trigger.lane_actions(frame.trigger, tuple(pc & ((1 << 50) - 1) for pc in pcs))
            prev_count = 1 if contract.uncache else expected.prev_count
            if contract.s1_moves:
                next_record = self._records[self._s1]
                prev_count = 1 if self._uncached(self._effective(next_record, frame)) else next_record.request.window.spec_count
            if contract.uncache:
                check_uncached_enqueue(sample.beat, record.effective, record.shift, response, record.carry_in,
                    prev_count=prev_count, trigger_actions=trigger_actions, fs_is_off=frame.fs_is_off)
                assert sample.gpa is None, 'uncached response cannot create a GPA translation write'
            else:
                check_enqueue(sample.beat, record.effective, record.shift, trigger_actions=trigger_actions,
                              prev_count=prev_count, fs_is_off=frame.fs_is_off)
                check_gpa(sample.gpa, record.effective, record.shift)
        else:
            assert sample.gpa is None, f'ifu.top.{phase}: unsolicited GPA write without a valid beat'
        assert sample.reasons == self._perf.output(), f'ifu.top.{phase}: wrong topdown reason history'

    def _events_for(self, frame, contract=None):
        contract = self._control(frame) if contract is None else contract
        has_beat = self._s2 is not None and not contract.s2_flush and (
            not contract.uncache or bool(contract.unit_outputs.resp_valid and not contract.resend))
        record = self._records[self._s2] if self._s2 is not None else None
        return event_counts(enqueue=has_beat and frame.ibuffer_ready, frontend_flush=contract.wb_redirect,
            hits=record.cache_hits if record is not None else (0, 0),
            double_line=record.double_line if record is not None else 0)

    def _check_events(self, sample, phase):
        expected = self._event_pipe[0]
        if expected is not None:
            Scoreboard(f'ifu.top.{phase}.performance').check(
                expected=dict(zip(EVENT_NAMES, expected)), actual=dict(zip(EVENT_NAMES, sample.performance)))

    def _half_after(self, record, *, redirected=False):
        w = record.request.window
        if redirected:
            prediction = cached_expectation(record.effective, record.shift)[1].redirect
            if not prediction.invalid_taken:
                return None
            block = int(bool(prediction.block_sel))
        else:
            block = int(bool(w.block1_valid))
        if not (w.half1 if block else w.half0):
            return None
        pc = (w.start1_pc + 2 * (w.size1 - 1)) if block else (w.start0_pc + 2 * (w.size0 - 1))
        index = ((w.line_offset1 + w.size1 - 1) if block else (w.line_offset0 + w.size0 - 1)) & 31
        return HalfInstruction(pc, (w.line1 if block else w.line0)[index], record.uid,
                               input_source=record.input_source)

    def _check_carry(self, request):
        if self._uncached(request):
            if self._half is not None and request.window.start0_pc != (self._half.pc + 2) & ((1 << 51) - 1):
                raise ValueError('uncached continuation must resume after the input-established low half')
            return  # The bus, not placeholder ICache data, supplies the high half.
        first = request.window.instructions[0]
        claimed = first.pc != request.window.start0_pc
        if claimed != (self._half is not None):
            raise ValueError('IFU carry history does not match the submitted instruction stream')
        if claimed:
            if first.pc != self._half.pc or first.raw_data & 0xffff != self._half.low:
                raise ValueError('IFU carry low half/PC lost input identity')

    def _advance(self, frame, sample, tick, offered_uid):
        contract = self._control(frame)
        self._event_pipe = (self._event_pipe[1], self._events_for(frame, contract))
        redirect, s2_flush, frontend_flush = contract.redirect, contract.s2_flush, contract.frontend_flush
        bpu, s1_moves, ready = contract.bpu, contract.s1_moves, contract.fetch_ready
        old_s1, old_s2 = self._s1, self._s2
        fire_uid = accepted_uid = beat_uid = redirect_uid = None
        if sample.beat is not None and frame.ibuffer_ready:
            record = self._records[old_s2]
            assert record.beat_tick is None, 'IFU repeated enqueue fire for a completed UID'
            self._records[old_s2] = replace(record, beat=sample.beat, gpa=sample.gpa, beat_tick=tick)
            self.beat_fires += 1
            beat_uid = old_s2
            self._first_instruction = False
        if sample.gpa is not None:
            self.gpa_writes += 1  # wen is valid-qualified, not ready-qualified.
        if sample.redirect is not None:
            record = self._records[contract.redirect_uid]
            assert record.redirect_tick is None, 'IFU repeated redirect for a completed UID'
            self._records[record.uid] = replace(record, redirect=sample.redirect, redirect_tick=tick)
            self.redirects += 1
            redirect_uid = record.uid
        bus_fire_uid = None
        if sample.bus is not None and frame.uncache_ready:
            assert self._unit_owner is not None, 'uncached bus issue without an input-established owner'
            record = self._records[self._unit_owner]
            assert record.issued_tick is None, 'duplicate uncached issue for the same accepted UID'
            self._records[record.uid] = replace(record, issued_tick=tick, bus=sample.bus)
            bus_fire_uid = record.uid
            self.bus_fires += 1
            self.flushed_bus_fires += int(s2_flush)
        if frame.reply is not None:
            self._seen_replies.add(frame.reply_uid)
            self.reply_fires += 1
            record = self._records[frame.reply_uid]
            self._records[record.uid] = replace(record, reply=frame.reply, reply_tick=tick, reply_source=frame.reply_source)
            if self._unit.phase != WAIT_RESP or s2_flush:
                self.ignored_replies += 1
        inputs, response = contract.unit_inputs, contract.unit_outputs
        if s2_flush:
            self._uncache_busy = False
            self._unit_owner = None
        elif inputs.req_valid and response.req_ready:
            assert old_s2 is not None, 'uncached child acceptance without a top-level owner'
            record = self._records[old_s2]
            assert record.unit_accepted_tick is None, 'uncached child accepted the same fetch twice'
            self._records[old_s2] = replace(record, unit_accepted_tick=tick)
            self._unit_owner, self._uncache_busy = old_s2, True
        elif response.resp_valid:
            self._uncache_busy = False
            self._unit_owner = None
        self._unit.tick(inputs)
        self._wb = old_s2 if self._s2_new and not s2_flush and not contract.uncache else None
        self._s2_new = False
        if s2_flush or beat_uid is not None or contract.resend:
            self._s2 = None
        if s1_moves and not frontend_flush:
            record = self._records[old_s1]
            # ECC belongs to the stage following request fire, not s0 data.
            effective = self._effective(record, frame)
            record = replace(record, effective=effective, pointer=self._pointer)
            self._records[old_s1] = record
            if not self._uncached(effective):
                self._pointer += cached_expectation(effective, record.shift)[0].prev_count
            self._s2, self._s2_new = old_s1, True
        if frame.backend_redirect:
            if self._half is not None:
                self._carry_cancellations.append(CarryCancellation(self._half, 'backend redirect', 'redirect', tick))
            self._pointer, self._half = 0, None
        elif redirect is not None:
            record = self._records[redirect_uid]
            if contract.uncache_redirect and redirect_uid == old_s2:
                self._pointer = record.pointer + int(not contract.resend)
                self._half = HalfInstruction(record.carry_in.pc if record.carry_in else record.request.window.start0_pc,
                    response.resp_data & 0xffff, record.uid,
                    'port-characterization' if record.reply_source == 'port-characterization' or (
                        record.carry_in is not None and record.carry_in.peer_source == 'port-characterization') else 'producer',
                    record.input_source) if contract.resend else None
                if contract.resend:
                    self._records[record.uid] = replace(record, state='resend', completion_source=self._half.peer_source)
            else:
                self._pointer = record.pointer + cached_expectation(record.effective, record.shift)[0].enq.bit_count()
                self._half = self._half_after(record, redirected=True)
        for uid, cancelled in ((old_s1, frontend_flush), (old_s2, s2_flush)):
            if uid is not None and cancelled:
                record = self._records[uid]
                self._records[uid] = replace(record, state='cancelled',
                    cancel_reason='backend redirect' if frame.backend_redirect else 'older frontend redirect')
        self._s1 = None if s1_moves or frontend_flush else old_s1
        if frame.request is not None and ready:
            fire_uid = offered_uid
            self.req_fires += 1
            dropped = frontend_flush or bpu
            record = FetchRecord(offered_uid, self._epoch, frame.request, tick, carry_in=self._half,
                state='cancelled-on-fire' if dropped else 'pending', cancel_reason='same-slot flush' if dropped else None,
                cache_hits=frame.cache_hits, double_line=frame.double_line)
            self._records[offered_uid] = record
            if dropped:
                self.cancelled_on_fire += 1
            else:
                self._check_carry(frame.request)
                self._s1 = accepted_uid = offered_uid
                if not self._uncached(frame.request):
                    self._half = self._half_after(record)
        elif frame.request is not None:
            record = self._records[offered_uid]
            self._records[offered_uid] = replace(record, state='not-accepted')
        for record in self.records:
            if record.state == 'pending' and record.beat_tick is not None and (
                    (not self._uncached(record.effective) and expected_redirect(record.effective, record.shift) is None)
                    or record.redirect_tick is not None):
                source = record.reply_source
                if record.carry_in is not None and record.carry_in.peer_source == 'port-characterization':
                    source = 'port-characterization'
                self._records[record.uid] = replace(record, state='completed', completion_source=source)
        self._trigger.tick(frame.trigger)
        self._perf.tick(replace(frame.reasons, ifu_wb_redirect=int(contract.wb_redirect)))
        self._audit()
        return fire_uid, accepted_uid, beat_uid, redirect_uid, bus_fire_uid

    def _audit(self):
        records = self.records
        fired = tuple(record for record in records if record.accepted_tick is not None)
        assert self.req_fires == len(fired), 'IFU physical fire/UID accounting mismatch'
        assert self.cancelled_on_fire == sum(record.state == 'cancelled-on-fire' for record in records), 'IFU same-slot cancellation accounting mismatch'
        effective = self.req_fires - self.cancelled_on_fire
        assert effective == sum(record.state in ('pending', 'completed', 'resend', 'cancelled') for record in fired), 'IFU lost an accepted fetch obligation'
        for counter, field in ((self.bus_fires, 'issued_tick'), (self.reply_fires, 'reply_tick'),
                               (self.beat_fires, 'beat_tick'), (self.redirects, 'redirect_tick')):
            assert counter == sum(getattr(record, field) is not None for record in records), f'IFU {field} event/UID accounting mismatch'
        for record in records:
            if record.state == 'completed':
                assert record.beat_tick is not None, 'IFU completed UID without enqueue fire'
                if self._uncached(record.effective):
                    assert record.unit_accepted_tick is not None and record.issued_tick is not None \
                        and record.reply_tick is not None and record.redirect_tick is not None, 'IFU uncached completion lost its issued/reply/redirect history'
            if record.state == 'resend':
                assert record.beat_tick is None and record.redirect_tick is not None \
                    and record.reply is not None and record.reply.need_resend, 'IFU resend was counted as an enqueue completion'
        for uid in (self._s1, self._s2, self._unit_owner):
            if uid is not None:
                assert uid in self._records and self._records[uid].state == 'pending', 'IFU active stage lost its pending UID'

    def _validate(self, frame):
        if not isinstance(frame, Frame):
            raise TypeError('IFU requires a semantic Frame')
        if frame.reset:
            raise ValueError('reset requires the explicit lifecycle operation and cancellation reason')
        if frame.reply is not None:
            self._validate_reply(frame)
        if frame.request is not None:
            contract = self._control(frame)
            if not contract.frontend_flush and not contract.bpu:
                self._check_carry(frame.request)
                identities = {frame.request.window.ftq0}
                if frame.request.window.block1_valid:
                    identities.add(frame.request.window.ftq1)
                live = {uid for uid in (self._s1, self._s2, self._wb) if uid is not None}
                for uid in live:
                    window = self._records[uid].request.window
                    pointers = {window.ftq0} | ({window.ftq1} if window.block1_valid else set())
                    if identities & pointers:
                        raise ValueError('IFU fetch cannot reuse a live FTQ identity before its stage retires or is cancelled')
                    if isinstance(frame.request, ProducerFetchRequest):
                        first = (frame.request.window.ftq0[0] << 6) | frame.request.window.ftq0[1]
                        for flag, value in pointers:
                            distance = (first - ((flag << 6) | value)) % 128
                            if not 0 < distance < 64:
                                raise ValueError('producer FTQ identity must be younger than every live stage within the unambiguous half-ring')
        candidate = list(self._trigger.triggers)
        if frame.trigger.update.valid:
            candidate[frame.trigger.update.index] = frame.trigger.update.trigger
        require_csr_table(candidate)

    def _validate_reply(self, frame):
        uid = frame.reply_uid
        if uid not in self._records or self._records[uid].issued_tick is None:
            raise ValueError('uncached reply requires a known actually issued UID')
        record = self._records[uid]
        if uid in self._seen_replies:
            raise ValueError('duplicate uncached reply UID')
        if uid != self._unit_owner or self._unit.phase != WAIT_RESP:
            if record.state != 'cancelled' or self._unit.phase == WAIT_RESP:
                raise ValueError('tagless uncached reply cannot be attributed to this live generation')
        if frame.reply_source == 'producer':
            request = ReadRequest(record.request.physical_address, record.request.window.pmp0, record.request.window.pbmt0)
            wanted = RequestLedger.expected_resend(request, frame.reply.data, frame.reply.corrupt)
            if frame.reply.need_resend != wanted:
                raise ValueError('InstrUncache producer needResend must match clean nonRVC page-final bytes')

    async def _cycle(self, frame, offered_uid=None):
        if frame.request is not None and offered_uid is None:
            self._uid += 1
            offered_uid = self._uid
        if frame.request is not None:
            self.offered_cycles += 1
            if offered_uid not in self._records:
                self._records[offered_uid] = FetchRecord(offered_uid, self._epoch, frame.request, None, state='offered')
        before, after = await self._exchange(frame)
        self._check_phase(frame, before.value, phase='before')
        events = self._advance(frame, before.value, before.event.tick, offered_uid)
        self._check_phase(frame, after.value, phase='after')
        self._sequence += 1
        return CheckedCycle(self._sequence, before.event.tick, after.event.tick, before.value, after.value,
                            *events[:4], offered_uid=offered_uid if frame.request is not None else None,
                            bus_fire_uid=events[4])

    async def cycle(self, frame=Frame()):
        self._validate(frame)
        self._enter()
        try:
            if not self._reset_done:
                raise RuntimeError('IFU requires an explicit reset before input')
            return await self._cycle(frame)
        except BaseException:
            self._failed = True
            raise
        finally:
            self._busy = False

    async def idle(self, cycles=1, *, frame=Frame()):
        if type(cycles) is not int or cycles < 1 or frame.request is not None:
            raise ValueError('idle requires positive cycles and no fetch request')
        last = None
        for _ in range(cycles):
            last = await self.cycle(frame)
        return last

    async def fetch(self, request, *, max_cycles=24, frame=Frame(), corruption=(0, 0, 0, 0)):
        if not isinstance(request, FetchRequest):
            raise TypeError('IFU fetch requires a FetchRequest')
        if self._uncached(request):
            raise ValueError('uncached fetch requires an explicit peer: send_uncached/reply/collect or read_uncached')
        if type(max_cycles) is not int or max_cycles < 1 or frame.request is not None:
            raise ValueError('fetch requires a positive cycle budget and request-free controls')
        if any(frame.corruption):
            raise ValueError('fetch ECC must use its explicit post-acceptance corruption argument')
        controls = replace(frame, corruption=corruption)
        self._validate(replace(frame, request=request))
        self._enter()
        try:
            if not self._reset_done:
                raise RuntimeError('IFU requires an explicit reset before input')
            self._uid += 1
            uid, accepted, ecc_sent = self._uid, False, False
            for _ in range(max_cycles):
                checked = await self._cycle(replace(controls if accepted and not ecc_sent else frame,
                    request=None if accepted else request), uid)
                ecc_sent |= accepted
                if checked.req_fire_uid == uid and checked.accepted_uid is None:
                    raise AssertionError(f'IFU promised fetch UID {uid} was cancelled on fire, not accepted')
                accepted |= checked.accepted_uid == uid
                record = self._records.get(uid)
                if record is not None and record.state == 'completed':
                    # Keep both monitors active and check every channel after
                    # the first result, including during the complete quiet tail.
                    for _ in range(4):
                        await self._cycle(frame)
                    return FetchResult(uid, record.beat, record.redirect, record.gpa,
                                       input_source=record.input_source)
            raise AssertionError(f'IFU fetch UID {uid} did not complete within {max_cycles} cycles; accepted={accepted}')
        except BaseException:
            self._failed = True
            raise
        finally:
            self._busy = False

    async def send_uncached(self, request, *, max_cycles=24, frame=Frame(uncache_ready=1)):
        """Return the input UID only after its actual public bus request fire."""
        if not isinstance(request, FetchRequest) or not self._uncached(request):
            raise ValueError('send_uncached requires a semantic MMIO/NC/IO fetch without an ICache exception')
        if type(max_cycles) is not int or max_cycles < 1 or frame.request is not None or frame.reply is not None:
            raise ValueError('send_uncached requires a positive cycle budget and request/reply-free controls')
        self._validate(replace(frame, request=request))
        self._enter()
        try:
            if not self._reset_done:
                raise RuntimeError('IFU requires an explicit reset before input')
            self._uid += 1
            uid, accepted = self._uid, False
            for _ in range(max_cycles):
                checked = await self._cycle(replace(frame, request=None if accepted else request), uid)
                if checked.req_fire_uid == uid and checked.accepted_uid is None:
                    raise AssertionError(f'IFU promised uncached UID {uid} was cancelled on fire, not accepted')
                accepted |= checked.accepted_uid == uid
                if checked.bus_fire_uid == uid:
                    return uid
            raise AssertionError(f'IFU uncached UID {uid} was not issued within {max_cycles} cycles; accepted={accepted}')
        except BaseException:
            self._failed = True
            raise
        finally:
            self._busy = False

    async def _reply(self, uid, response, frame, source):
        if not isinstance(response, BusReply):
            raise TypeError('uncached reply requires a semantic BusReply')
        if frame.reply is not None:
            raise ValueError('reply controls cannot provide a second reply')
        return await self.cycle(replace(frame, reply=response, reply_uid=uid, reply_source=source))

    async def reply(self, uid, response, *, frame=Frame()):
        """Real peer rule: only clean, full-width data at the final page half resends."""
        return await self._reply(uid, response, frame, 'producer')

    async def characterize_reply(self, uid, response, *, frame=Frame()):
        """Explicit peer-port pressure; still issued-UID/schema/phase/compare checked."""
        return await self._reply(uid, response, frame, 'port-characterization')

    async def collect(self, uid, *, max_cycles=24, frame=Frame()):
        if type(uid) is not int or uid not in self._records:
            raise ValueError('collect requires a known input-established UID')
        if type(max_cycles) is not int or max_cycles < 1 or frame.request is not None or frame.reply is not None:
            raise ValueError('collect requires positive cycles and request/reply-free controls')
        self._validate(frame)
        self._enter()
        try:
            for _ in range(max_cycles):
                record = self._records[uid]
                if record.state in ('completed', 'resend'):
                    for _ in range(4):
                        await self._cycle(frame)
                    return FetchResult(uid, record.beat, record.redirect, record.gpa, record.bus,
                                       int(record.state == 'resend'), record.completion_source, record.input_source)
                assert record.state not in ('cancelled', 'cancelled-on-fire'), 'cancelled fetch is not a completed result'
                await self._cycle(frame)
            raise AssertionError(f'IFU collect UID {uid} did not complete within {max_cycles} cycles')
        except BaseException:
            self._failed = True
            raise
        finally:
            self._busy = False

    async def read_uncached(self, request, response, *, max_cycles=24, frame=Frame(uncache_ready=1)):
        if not isinstance(request, FetchRequest) or not isinstance(response, BusReply):
            raise TypeError('read_uncached requires FetchRequest and BusReply')
        wanted = RequestLedger.expected_resend(
            ReadRequest(request.physical_address, request.window.pmp0, request.window.pbmt0), response.data, response.corrupt)
        if response.need_resend != wanted:
            raise ValueError('InstrUncache producer needResend must match clean nonRVC page-final bytes')
        uid = await self.send_uncached(request, max_cycles=max_cycles, frame=frame)
        await self.reply(uid, response, frame=replace(frame, uncache_ready=0))
        return await self.collect(uid, max_cycles=max_cycles, frame=replace(frame, uncache_ready=0))

    async def cancel_pending(self, reason):
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError('IFU cancellation requires a nonempty reason')
        cancelled = self.outstanding
        half = self._half
        await self.cycle(Frame(backend_redirect=1))
        if half is not None:
            self._carry_cancellations[-1] = replace(self._carry_cancellations[-1], reason=reason, operation='cancel')
        for uid in cancelled:
            if self._records[uid].state == 'cancelled':
                self._records[uid] = replace(self._records[uid], cancel_reason=reason)
        await self.idle(4)

    async def finish(self, max_cycles=8):
        if self._finished:
            return
        if type(max_cycles) is not int or max_cycles < 1:
            raise ValueError('finish requires a positive cycle budget')
        self._enter()
        try:
            if not self._reset_done:
                raise RuntimeError('IFU requires an explicit reset before finish')
            for _ in range(max_cycles):
                await self._cycle(Frame())
            assert not self.outstanding, f'IFU finish left outstanding fetch UIDs {self.outstanding}'
            assert self._half is None, 'IFU finish left an incomplete carry instruction; complete or explicitly cancel it'
            assert self._unit_owner is None and self._unit.phase == 'idle' and not self._unit.finish, 'IFU finish left an uncached peer obligation'
            assert self._event_pipe == ((0,) * 13, (0,) * 13), 'IFU finish left an unsettled performance event tail'
            assert self._s1 is None and self._s2 is None and self._wb is None, 'IFU finish left a live stage history'
            self._audit()
            self._finished = True
        except BaseException:
            self._failed = True
            raise
        finally:
            self._busy = False
