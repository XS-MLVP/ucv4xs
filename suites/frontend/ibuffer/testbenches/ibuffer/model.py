"""Independent IBuffer queue/vtype model.

The architectural behaviour is written from the IBuffer interface contract and
the RISC-V V specification, not from the generated RTL:

* 48-entry circular instruction queue with 4 write banks, 8 read banks and a
  36-lane IFU enqueue beat.  The IFU pre-aligns the beat so the first enqueued
  lane sits at ``enqPtr % 4``; the remaining lanes map to consecutive queue
  positions.
* ``allowEnq`` is the flow-control register: it is true exactly when the
  *previous* cycle announced fewer incoming instructions than the number of
  slots that will be free after this cycle's enqueue and dequeue.
* ``empty``/``full`` and the head-only output window follow the queue pointers;
  ``outputEntries`` is a 8-entry staging window that is refilled from the read
  banks (or directly from the IFU beat in "bypass" mode).
* Bypass is only legal when the queue is empty, decode accepts, and the beat
  carries no ``vset{i}vl{i}``.  A bypassed instruction receives the current
  speculated vtype; because a vset would change it, the beat is queued instead.
* The embedded VTypeGen is the real speculation engine: the model runs the
  same independent vtype oracle as the leaf DUT and feeds it the exact lanes
  that the queue is about to hand to decode.
* ``flush`` discards the staging window and resets every queue pointer.

The model keeps the bank/in-bank pointers as well so data selection follows
the documented banked-read structure instead of a shortcut.
"""

from __future__ import annotations

from dataclasses import dataclass, replace, field

from suites.frontend.ibuffer.testbenches.vtype_gen.model import INIT_VTYPE
from suites.frontend.ibuffer.testbenches.vtype_gen.model import StimulusError
from suites.frontend.ibuffer.testbenches.vtype_gen.model import VType
from suites.frontend.ibuffer.testbenches.vtype_gen.model import VTypeGenModel
from suites.frontend.ibuffer.testbenches.vtype_gen.model import binary
from suites.frontend.ibuffer.testbenches.vtype_gen.model import is_vsetivli
from suites.frontend.ibuffer.testbenches.vtype_gen.model import is_vsetvl
from suites.frontend.ibuffer.testbenches.vtype_gen.model import is_vsetvli

SIZE = 48
NUM_WRITE_BANK = 4
NUM_READ_BANK = 8
READ_BANK_SIZE = SIZE // NUM_READ_BANK
WRITE_BANK_SIZE = SIZE // NUM_WRITE_BANK
ENQUEUE_WIDTH = 36
DECODE_WIDTH = 8
MAX_BYPASS = 12
#: IFU fetch block is 64 B with C extension -> 32 instruction slots.
FETCH_SLOTS = 32
#: Lanes 32..35 are the write-bank padding the IFU drives as zero.
PAYLOAD_LANES = FETCH_SLOTS

#: TopDownCounters.FetchFragBubble.id (package.scala).
FETCH_FRAG_BUBBLE = 13
#: TopDownCounters.NumStallReasons.id.
NUM_STALL_REASONS = 76
BTB_MISS_BUBBLE = 12
TAGE_MISS_BUBBLE = 3
SC_MISS_BUBBLE = 4
ITTAGE_MISS_BUBBLE = 5
RAS_MISS_BUBBLE = 6
MEM_VIO_REDIRECT_BUBBLE = 7
OTHER_REDIRECT_BUBBLE = 8

#: ExceptionType.Value used by the frontend (Bundles.scala).
EXC_NONE = 0
EXC_PF = 1
EXC_GPF = 2
EXC_AF = 3
EXC_ILL = 4
EXC_HWE = 5
EXCEPTION_NAMES = {EXC_NONE: "none", EXC_PF: "page-fault", EXC_GPF: "guest-page-fault",
                   EXC_AF: "access-fault", EXC_ILL: "illegal-instruction",
                   EXC_HWE: "hardware-error"}

ZERO_ENTRY = None  # filled below


def popcount(value: int) -> int:
    return bin(value).count("1")


def low_bit_index(value: int) -> int:
    if value == 0:
        return 0
    return (value & -value).bit_length() - 1


def high_bit_index(value: int) -> int:
    return value.bit_length() - 1 if value else 0


def _run(value: int, name: str) -> tuple[int, int]:
    """Return (start, length) for a contiguous lane mask."""
    if not isinstance(value, int) or value < 0 or value >= (1 << ENQUEUE_WIDTH):
        raise StimulusError(f"{name} must be a {ENQUEUE_WIDTH}-bit lane mask")
    if value == 0:
        return 0, 0
    start = low_bit_index(value)
    length = 0
    while value >> (start + length) & 1:
        length += 1
    if value != ((1 << length) - 1) << start:
        raise StimulusError(f"{name} must be one contiguous lane run")
    return start, length


def _onehot(value: int, name: str) -> int:
    if not isinstance(value, int) or value < 0 or value >= (1 << ENQUEUE_WIDTH):
        raise StimulusError(f"{name} must be a {ENQUEUE_WIDTH}-bit lane mask")
    if value and value & (value - 1):
        raise StimulusError(f"{name} must be zero or a single lane")
    return value


@dataclass(frozen=True)
class FetchEntry:
    """One instruction as delivered by the IFU on an enqueue lane."""

    inst: int = 0
    is_rvc: int = 0
    foldpc: int = 0
    pred_taken: int = 0
    offset: int = 0
    ftq_flag: int = 0
    ftq_value: int = 0
    triggered: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.inst, int) or not 0 <= self.inst < (1 << 32):
            raise StimulusError("inst must be an unsigned 32-bit value")
        for name in ("is_rvc", "pred_taken", "ftq_flag"):
            binary(getattr(self, name), name)
        if not isinstance(self.foldpc, int) or not 0 <= self.foldpc < (1 << 10):
            raise StimulusError("foldpc must be 10 bits")
        if not isinstance(self.offset, int) or not 0 <= self.offset < (1 << 5):
            raise StimulusError("instrEndOffset must be 5 bits")
        if not isinstance(self.ftq_value, int) or not 0 <= self.ftq_value < (1 << 6):
            raise StimulusError("ftqPtr value must be 6 bits")
        if not isinstance(self.triggered, int) or not 0 <= self.triggered < (1 << 4):
            raise StimulusError("trigger action must be 4 bits")


ZERO_ENTRY = FetchEntry()


@dataclass(frozen=True)
class ExceptionEntry:
    """The block-0 frontend exception carried next to one fetch beat."""

    exc_type: int = EXC_NONE
    cross_page: int = 0
    backend_exception: int = 0
    satp_flush: int = 0

    def __post_init__(self) -> None:
        if self.exc_type not in EXCEPTION_NAMES:
            raise StimulusError(f"unknown exception type {self.exc_type}")
        for name in ("cross_page", "backend_exception", "satp_flush"):
            binary(getattr(self, name), name)

    @property
    def has_exception(self) -> bool:
        return self.exc_type != EXC_NONE

    def bits(self) -> dict[str, int]:
        """Map to the five architectural exception bits the IBuffer exports."""
        return {
            "exc_page_fault": int(self.exc_type == EXC_PF),
            "exc_guest_page_fault": int(self.exc_type == EXC_GPF),
            "exc_access_fault": int(self.exc_type == EXC_AF),
            "exc_illegal": int(self.exc_type == EXC_ILL),
            "exc_hardware_error": int(self.exc_type == EXC_HWE),
        }


ZERO_EXCEPTION = ExceptionEntry()


@dataclass(frozen=True)
class OutputEntry:
    valid: int = 0
    entry: FetchEntry = ZERO_ENTRY
    exception: ExceptionEntry = ZERO_EXCEPTION
    vtype: VType = INIT_VTYPE
    specvtype: VType = INIT_VTYPE


@dataclass(frozen=True)
class Inputs:
    """One encoded cycle of IBuffer stimulus (lane masks already aligned)."""

    reset: int = 0
    flush: int = 0
    in_valid: int = 0
    valid: int = 0
    enq_enable: int = 0
    entries: tuple[FetchEntry, ...] = (ZERO_ENTRY,) * ENQUEUE_WIDTH
    exception_mask: int = 0
    exception: ExceptionEntry = ZERO_EXCEPTION
    prev_instr_count: int = 0
    decode_can_accept: int = 0
    resuming_vtype: int = 0
    walk_to_arch_vtype: int = 0
    walk_vtype_valid: int = 0
    walk_vtype: VType = INIT_VTYPE
    vsetvl_vtype: VType = INIT_VTYPE
    commit_vtype_valid: int = 0
    commit_vtype: VType = INIT_VTYPE
    commit_has_vsetvl: int = 0
    topdown_reasons: int = 0
    backend_redirect: int = 0
    control_flow_redirect: int = 0
    memory_violation_redirect: int = 0
    tage_miss_bubble: int = 0
    ittage_miss_bubble: int = 0
    ras_miss_bubble: int = 0

    def __post_init__(self) -> None:
        for name in ("reset", "flush", "in_valid", "decode_can_accept",
                     "resuming_vtype", "walk_to_arch_vtype", "walk_vtype_valid",
                     "commit_vtype_valid", "commit_has_vsetvl",
                     "backend_redirect", "control_flow_redirect",
                     "memory_violation_redirect", "tage_miss_bubble",
                     "ittage_miss_bubble", "ras_miss_bubble"):
            binary(getattr(self, name), name)
        _run(self.valid, "valid")
        _run(self.enq_enable, "enq_enable")
        if self.enq_enable & ~self.valid:
            raise StimulusError("enqEnable must be a subset of valid")
        if self.valid >> PAYLOAD_LANES:
            raise StimulusError("the IFU never marks lanes 32..35 valid")
        if not isinstance(self.entries, tuple) or len(self.entries) != ENQUEUE_WIDTH:
            raise StimulusError(f"entries must hold {ENQUEUE_WIDTH} lanes")
        for entry in self.entries:
            if not isinstance(entry, FetchEntry):
                raise StimulusError("entries must be FetchEntry values")
        if not isinstance(self.exception, ExceptionEntry):
            raise StimulusError("exception must be an ExceptionEntry")
        _onehot(self.exception_mask, "exception_mask")
        if not isinstance(self.prev_instr_count, int) or not 0 <= self.prev_instr_count < 64:
            raise StimulusError("prevInstrCount must be 6 bits")
        if not isinstance(self.topdown_reasons, int) or not 0 <= self.topdown_reasons < (1 << 76):
            raise StimulusError("topdown reasons must be 76 bits")
        for name in ("walk_vtype", "vsetvl_vtype", "commit_vtype"):
            if not isinstance(getattr(self, name), VType):
                raise StimulusError(f"{name} must be a VType")
        if self.in_valid == 0 and (self.valid or self.enq_enable or self.exception_mask
                                   or self.exception.has_exception):
            raise StimulusError("a quiet beat must not carry fetch payload")


@dataclass(frozen=True)
class Beat:
    """Semantic fetch beat; the agent places it at the current ALIGN offset."""

    entries: tuple[FetchEntry, ...] = ()
    enq_count: int | None = None
    exception: ExceptionEntry = ZERO_EXCEPTION
    in_valid: int = 1
    decode_can_accept: int = 0
    resuming_vtype: int = 0
    walk_to_arch_vtype: int = 0
    walk_vtype_valid: int = 0
    walk_vtype: VType = INIT_VTYPE
    vsetvl_vtype: VType = INIT_VTYPE
    commit_vtype_valid: int = 0
    commit_vtype: VType = INIT_VTYPE
    commit_has_vsetvl: int = 0
    topdown_reasons: int = 0
    backend_redirect: int = 0
    control_flow_redirect: int = 0
    memory_violation_redirect: int = 0
    tage_miss_bubble: int = 0
    ittage_miss_bubble: int = 0
    ras_miss_bubble: int = 0
    flush: int = 0

    @property
    def count(self) -> int:
        return len(self.entries) if self.enq_count is None else self.enq_count

    def __post_init__(self) -> None:
        if not isinstance(self.entries, tuple):
            raise StimulusError("entries must be a tuple")
        for entry in self.entries:
            if not isinstance(entry, FetchEntry):
                raise StimulusError("entries must be FetchEntry values")
        if len(self.entries) > FETCH_SLOTS:
            raise StimulusError(f"one IFU beat carries at most {FETCH_SLOTS} instructions")
        if not 0 <= self.count <= len(self.entries):
            raise StimulusError("enq_count must not exceed the delivered instructions")
        for name in ("in_valid", "decode_can_accept", "resuming_vtype",
                     "walk_to_arch_vtype", "walk_vtype_valid",
                     "commit_vtype_valid", "commit_has_vsetvl", "flush",
                     "backend_redirect", "control_flow_redirect",
                     "memory_violation_redirect", "tage_miss_bubble",
                     "ittage_miss_bubble", "ras_miss_bubble"):
            binary(getattr(self, name), name)
        if not isinstance(self.exception, ExceptionEntry):
            raise StimulusError("exception must be an ExceptionEntry")
        if self.in_valid == 0 and (self.entries or self.exception.has_exception):
            raise StimulusError("a quiet beat must not carry fetch payload")

    def to_inputs(self, offset: int, *, prev_instr_count: int = 0) -> Inputs:
        """Place the semantic beat at the IFU write-bank alignment lane."""
        if not 0 <= offset < NUM_WRITE_BANK:
            raise StimulusError("alignment offset must be one write bank")
        if self.in_valid == 0:
            return Inputs(prev_instr_count=prev_instr_count,
                          decode_can_accept=self.decode_can_accept,
                          resuming_vtype=self.resuming_vtype,
                          walk_to_arch_vtype=self.walk_to_arch_vtype,
                          walk_vtype_valid=self.walk_vtype_valid,
                          walk_vtype=self.walk_vtype,
                          vsetvl_vtype=self.vsetvl_vtype,
                          commit_vtype_valid=self.commit_vtype_valid,
                          commit_vtype=self.commit_vtype,
                          commit_has_vsetvl=self.commit_has_vsetvl,
                          topdown_reasons=self.topdown_reasons,
                          backend_redirect=self.backend_redirect,
                          control_flow_redirect=self.control_flow_redirect,
                          memory_violation_redirect=self.memory_violation_redirect,
                          tage_miss_bubble=self.tage_miss_bubble,
                          ittage_miss_bubble=self.ittage_miss_bubble,
                          ras_miss_bubble=self.ras_miss_bubble,
                          flush=self.flush)
        delivered = len(self.entries)
        if offset + delivered > PAYLOAD_LANES:
            raise StimulusError("beat does not fit in the 32 IFU instruction slots")
        valid = ((1 << delivered) - 1) << offset
        enq_enable = ((1 << self.count) - 1) << offset
        lanes = [ZERO_ENTRY] * ENQUEUE_WIDTH
        for index, entry in enumerate(self.entries):
            lanes[offset + index] = entry
        return Inputs(
            flush=self.flush,
            in_valid=1,
            valid=valid,
            enq_enable=enq_enable,
            entries=tuple(lanes),
            exception_mask=1 << offset,
            exception=self.exception,
            prev_instr_count=prev_instr_count,
            decode_can_accept=self.decode_can_accept,
            resuming_vtype=self.resuming_vtype,
            walk_to_arch_vtype=self.walk_to_arch_vtype,
            walk_vtype_valid=self.walk_vtype_valid,
            walk_vtype=self.walk_vtype,
            vsetvl_vtype=self.vsetvl_vtype,
            commit_vtype_valid=self.commit_vtype_valid,
            commit_vtype=self.commit_vtype,
            commit_has_vsetvl=self.commit_has_vsetvl,
            topdown_reasons=self.topdown_reasons,
            backend_redirect=self.backend_redirect,
            control_flow_redirect=self.control_flow_redirect,
            memory_violation_redirect=self.memory_violation_redirect,
            tage_miss_bubble=self.tage_miss_bubble,
            ittage_miss_bubble=self.ittage_miss_bubble,
            ras_miss_bubble=self.ras_miss_bubble,
        )


@dataclass(frozen=True)
class LaneOutputs:
    valid: int
    instr: int
    foldpc: int
    is_rvc: int
    pred_taken: int
    ftq_flag: int
    ftq_value: int
    ftq_offset: int
    trigger: int
    cross_page_ipf_fix: int
    backend_exception: int
    satp_flush_first_fetch_fault: int
    exc_page_fault: int
    exc_guest_page_fault: int
    exc_access_fault: int
    exc_illegal: int
    exc_hardware_error: int
    vtype: VType
    specvtype: VType

    def payload(self) -> dict[str, int]:
        data = {"instr": self.instr, "foldpc": self.foldpc,
                "is_rvc": self.is_rvc, "pred_taken": self.pred_taken,
                "ftq_flag": self.ftq_flag, "ftq_value": self.ftq_value,
                "ftq_offset": self.ftq_offset, "trigger": self.trigger,
                "cross_page_ipf_fix": self.cross_page_ipf_fix,
                "backend_exception": self.backend_exception,
                "satp_flush_first_fetch_fault": self.satp_flush_first_fetch_fault,
                "exc_page_fault": self.exc_page_fault,
                "exc_guest_page_fault": self.exc_guest_page_fault,
                "exc_access_fault": self.exc_access_fault,
                "exc_illegal": self.exc_illegal,
                "exc_hardware_error": self.exc_hardware_error}
        data.update({f"vtype_{key}": value for key, value in self.vtype.as_dict().items()})
        data.update({f"specvtype_{key}": value
                     for key, value in self.specvtype.as_dict().items()})
        return data


@dataclass(frozen=True)
class Outputs:
    in_ready: int
    full: int
    empty: int
    lanes: tuple[LaneOutputs, ...]
    stall_reason: tuple[int, ...]


@dataclass(frozen=True)
class Events:
    fire: int
    num_enq: int
    num_out: int
    use_bypass: int
    flush: int
    deq_has_exception: int
    receive_exception: int


def reset_outputs() -> Outputs:
    lane = LaneOutputs(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                       0, 0, 0, 0, 0, INIT_VTYPE, INIT_VTYPE)
    return Outputs(in_ready=1, full=0, empty=1,
                   lanes=tuple(lane for _ in range(DECODE_WIDTH)),
                   stall_reason=(0,) * DECODE_WIDTH)


def _lane_outputs(entry: OutputEntry) -> LaneOutputs:
    bits = entry.exception.bits()
    return LaneOutputs(
        valid=entry.valid,
        instr=entry.entry.inst,
        foldpc=entry.entry.foldpc,
        is_rvc=entry.entry.is_rvc,
        pred_taken=entry.entry.pred_taken,
        ftq_flag=entry.entry.ftq_flag,
        ftq_value=entry.entry.ftq_value,
        ftq_offset=entry.entry.offset,
        trigger=entry.entry.triggered,
        cross_page_ipf_fix=entry.exception.cross_page,
        backend_exception=entry.exception.backend_exception,
        satp_flush_first_fetch_fault=int(entry.exception.satp_flush
                                         and entry.exception.has_exception),
        exc_page_fault=bits["exc_page_fault"],
        exc_guest_page_fault=bits["exc_guest_page_fault"],
        exc_access_fault=bits["exc_access_fault"],
        exc_illegal=bits["exc_illegal"],
        exc_hardware_error=bits["exc_hardware_error"],
        vtype=entry.vtype,
        specvtype=entry.specvtype,
    )


class IBufferModel:
    def __init__(self) -> None:
        self.vtype = VTypeGenModel()
        self.reset_state()

    # -- reset --------------------------------------------------------------
    def reset_state(self) -> None:
        self.ibuf: list[FetchEntry] = [ZERO_ENTRY] * SIZE
        self.deq_bank_ptr = list(range(NUM_READ_BANK))
        self.deq_in_bank_ptr = [0] * NUM_READ_BANK
        self.deq_ptr = list(range(DECODE_WIDTH))
        self.enq_ptr = 0
        self.ifu_aligned = list(range(ENQUEUE_WIDTH))
        self.output_entries = [OutputEntry() for _ in range(DECODE_WIDTH)]
        self.first_exc_valid = 0
        self.first_exc = ZERO_EXCEPTION
        self.first_exc_idx = 0
        self.allow_enq = 1
        self.topdown = [0, 0]
        self.vtype.reset_state()

    # -- helpers ------------------------------------------------------------
    def _override(self, reasons: int, inputs: Inputs) -> int:
        """Apply BackendRedirectTopdown to one top-down stage.

        ``btbMissBubble``/``scMissBubble`` are pruned at the IBuffer boundary
        (not exported), so a control-flow redirect clears those two reasons.
        """
        if not inputs.backend_redirect:
            return reasons
        if inputs.control_flow_redirect:
            reasons &= ~(1 << BTB_MISS_BUBBLE)
            reasons &= ~(1 << SC_MISS_BUBBLE)
            for bit, value in ((TAGE_MISS_BUBBLE, inputs.tage_miss_bubble),
                               (ITTAGE_MISS_BUBBLE, inputs.ittage_miss_bubble),
                               (RAS_MISS_BUBBLE, inputs.ras_miss_bubble)):
                reasons = (reasons | (1 << bit)) if value else (reasons & ~(1 << bit))
            return reasons
        if inputs.memory_violation_redirect:
            return reasons | (1 << MEM_VIO_REDIRECT_BUBBLE)
        return reasons | (1 << OTHER_REDIRECT_BUBBLE)

    def _stall_reason(self) -> tuple[int, ...]:
        """Highest active top-down reason per wasted output lane.

        The generated matchBubble is ``0`` when no reason is active; the
        FetchFragBubble fallback only applies when at least one lane is
        occupied (an all-empty window maps every lane to 0).
        """
        valid_count = sum(entry.valid for entry in self.output_entries)
        waste = DECODE_WIDTH - valid_count
        if waste == 0:
            return (0,) * DECODE_WIDTH
        last = self.topdown[1]
        if last:
            bubble = high_bit_index(last)
        elif waste == DECODE_WIDTH:
            bubble = 0
        else:
            bubble = FETCH_FRAG_BUBBLE
        reason = [0] * DECODE_WIDTH
        for index in range(waste):
            reason[DECODE_WIDTH - index - 1] = bubble
        return tuple(reason)

    def _check_alignment(self, inputs: Inputs) -> int:
        start, length = _run(inputs.enq_enable, "enq_enable")
        if length == 0:
            return 0
        if start != self.enq_ptr % NUM_WRITE_BANK:
            raise StimulusError(
                f"IFU beat starts at lane {start} but enqPtr%4 is "
                f"{self.enq_ptr % NUM_WRITE_BANK}")
        if inputs.exception_mask not in (0, 1 << start):
            raise StimulusError("exceptionMask must point at the first enqueued lane")
        targets = [self.ifu_aligned[low_bit_index(inputs.enq_enable) + i] for i in range(length)]
        if len(set(targets)) != len(targets):
            raise StimulusError("IFU pre-alignment produced duplicate write targets")
        return start

    # -- combinational evaluation ------------------------------------------
    def _evaluate(self, inputs: Inputs) -> dict:
        start = self._check_alignment(inputs)
        enq = self.enq_ptr
        deq = self.deq_ptr[0]
        num_valid = (enq - deq) % SIZE
        fire = int(bool(inputs.in_valid) and bool(self.allow_enq))
        num_try_enq = popcount(inputs.enq_enable) if inputs.in_valid else 0
        num_enq = num_try_enq if fire else 0

        enq_has_vset = bool(inputs.in_valid) and any(
            inputs.valid >> lane & 1 and inputs.enq_enable >> lane & 1
            and (is_vsetvli(inputs.entries[lane].inst)
                 or is_vsetivli(inputs.entries[lane].inst)
                 or is_vsetvl(inputs.entries[lane].inst))
            for lane in range(PAYLOAD_LANES))

        queue_empty = enq == deq
        use_bypass = int(queue_empty and inputs.decode_can_accept
                         and not inputs.resuming_vtype and not enq_has_vset)

        # PriorityMuxDefault over (valid_i, i+1) reversed: the highest valid
        # lane in 0..6 reports its count.  Lane 7 is not in the priority list
        # because a full window takes the replace path, never the append one.
        output_valid_num = 0
        for lane in range(DECODE_WIDTH - 2, -1, -1):
            if self.output_entries[lane].valid:
                output_valid_num = lane + 1
                break
        output_is_not_full = not self.output_entries[DECODE_WIDTH - 1].valid

        maybe_bypass = (popcount(inputs.enq_enable & ((1 << MAX_BYPASS) - 1))
                        if inputs.in_valid else 0)
        num_bypass = min(maybe_bypass, DECODE_WIDTH) if use_bypass else 0

        if inputs.resuming_vtype:
            num_out = 0
        elif inputs.decode_can_accept:
            num_out = num_bypass if use_bypass else min(num_valid, DECODE_WIDTH)
        elif output_is_not_full:
            num_out = min(num_valid, DECODE_WIDTH - output_valid_num)
        else:
            num_out = 0
        next_num_valid = num_valid + num_enq - num_out
        if not 0 <= next_num_valid <= SIZE:
            raise StimulusError("this beat overflows the 48-entry queue")
        allow_enq_next = int(inputs.prev_instr_count < SIZE - next_num_valid)

        # Banked read of the num_out dequeued instructions.
        read_stage1 = [
            self.ibuf[bank + self.deq_in_bank_ptr[bank] * NUM_READ_BANK]
            for bank in range(NUM_READ_BANK)
        ]
        deq_bits = []
        deq_valid = []
        for lane in range(DECODE_WIDTH):
            bank = self.deq_bank_ptr[lane]
            index = bank + self.deq_in_bank_ptr[bank] * NUM_READ_BANK
            if index != self.deq_ptr[lane]:
                raise AssertionError("bank pointer invariant violated")
            deq_bits.append(read_stage1[bank])
            deq_valid.append(int(lane < num_out and not use_bypass))

        # Bypass window reads IFU lanes starting at the enqueue alignment.
        bypass = []
        bypass_exc_mask = []
        for slot in range(DECODE_WIDTH):
            lane = start + slot
            selected = (inputs.valid >> lane & 1 and inputs.enq_enable >> lane & 1)
            bypass.append(OutputEntry(
                valid=int(bool(selected) and bool(fire) and not inputs.flush),
                entry=inputs.entries[lane],
            ))
            bypass_exc_mask.append(int(selected and (inputs.exception_mask >> lane & 1)))

        # Exception of the dequeued group (attached to the matching pointer).
        deq_exception_offset = 0
        deq_exception = False
        for lane in range(num_out):
            if self.first_exc_valid and self.deq_ptr[lane] == self.first_exc_idx:
                deq_exception = True
                deq_exception_offset = lane
                break

        # Staging window refill.
        out_from_deq: list[OutputEntry] = []
        for lane in range(DECODE_WIDTH):
            if inputs.decode_can_accept and not inputs.resuming_vtype:
                exception = (self.first_exc if deq_exception
                             and lane == deq_exception_offset else ZERO_EXCEPTION)
                out_from_deq.append(OutputEntry(deq_valid[lane], deq_bits[lane],
                                                exception))
            elif output_is_not_full and not inputs.resuming_vtype:
                if lane < output_valid_num:
                    out_from_deq.append(self.output_entries[lane])
                else:
                    position = lane - output_valid_num
                    valid = int(position < num_out)
                    exception = (self.first_exc if deq_exception
                                 and position == deq_exception_offset
                                 else ZERO_EXCEPTION)
                    out_from_deq.append(OutputEntry(valid, deq_bits[position], exception))
            else:
                out_from_deq.append(self.output_entries[lane])

        out_next = list(out_from_deq)
        if inputs.decode_can_accept and not inputs.resuming_vtype \
                and use_bypass and inputs.in_valid:
            for lane in range(DECODE_WIDTH):
                out_next[lane] = OutputEntry(
                    bypass[lane].valid, bypass[lane].entry,
                    inputs.exception if bypass_exc_mask[lane] else ZERO_EXCEPTION)

        # The real VTypeGen consumes exactly the lanes entering the window.
        vg_lanes = []
        for lane in range(DECODE_WIDTH):
            if inputs.resuming_vtype:
                valid = 0
            elif inputs.decode_can_accept:
                valid = out_from_deq[lane].valid
            elif output_is_not_full:
                valid = int(lane >= output_valid_num
                            and lane - output_valid_num < num_out)
            else:
                valid = 0
            vg_lanes.append((valid, out_from_deq[lane].entry.inst))
        vg_inputs = _VTypeInputs(
            insts=tuple(vg_lanes),
            walk_to_arch_vtype=inputs.walk_to_arch_vtype,
            walk_vtype_valid=inputs.walk_vtype_valid,
            walk_vtype=inputs.walk_vtype,
            can_update_vtype=int(not inputs.resuming_vtype
                                 and (inputs.decode_can_accept or output_is_not_full)),
            vsetvl_vtype=inputs.vsetvl_vtype,
            commit_vtype_valid=inputs.commit_vtype_valid,
            commit_vtype=inputs.commit_vtype,
            commit_has_vsetvl=inputs.commit_has_vsetvl,
        )
        vg_out = self.vtype.outputs(vg_inputs)

        for lane in range(DECODE_WIDTH):
            if inputs.decode_can_accept and not inputs.resuming_vtype:
                out_next[lane] = replace(out_next[lane],
                                         vtype=vg_out.vtype[lane],
                                         specvtype=vg_out.specvtype[lane])
            elif output_is_not_full and not inputs.resuming_vtype \
                    and lane >= output_valid_num:
                out_next[lane] = replace(out_next[lane],
                                         vtype=vg_out.vtype[lane],
                                         specvtype=vg_out.specvtype[lane])

        if inputs.flush:
            out_next = [replace(entry, valid=0) for entry in out_next]

        # Exception bookkeeping.
        first_valid = self.first_exc_valid
        first_bits = self.first_exc
        first_idx = self.first_exc_idx
        if not first_valid:
            first_bits = inputs.exception
            first_idx = self.ifu_aligned[low_bit_index(inputs.exception_mask)]
        receive = int(bool(fire) and not inputs.flush and not first_valid
                      and inputs.exception.has_exception
                      and bool(inputs.exception_mask & inputs.enq_enable)
                      and (not use_bypass or not any(bypass_exc_mask)))
        if receive:
            first_valid = 1
        if deq_exception and not inputs.resuming_vtype \
                and (inputs.decode_can_accept or output_is_not_full):
            first_valid = 0
        if inputs.flush:
            # The flush block clears the stored exception together with the
            # queue and the staging window.
            first_valid = 0

        events = Events(fire=fire, num_enq=num_enq, num_out=num_out,
                        use_bypass=use_bypass, flush=inputs.flush,
                        deq_has_exception=int(deq_exception),
                        receive_exception=receive)
        return dict(inputs=inputs, start=start, fire=fire, num_enq=num_enq,
                    num_out=num_out, use_bypass=use_bypass,
                    num_valid=num_valid, next_num_valid=next_num_valid,
                    allow_enq_next=allow_enq_next,
                    output_valid_num=output_valid_num,
                    output_is_not_full=output_is_not_full,
                    out_next=out_next, vg_inputs=vg_inputs,
                    first_valid_next=first_valid,
                    first_bits_next=first_bits,
                    first_idx_next=first_idx,
                    events=events,
                    deq_exception_offset=deq_exception_offset)

    # -- cycle interface ----------------------------------------------------
    def _registered_outputs(self) -> Outputs:
        """Every IBuffer output is driven by a register (or by registers).

        The generated module registers the output window, the queue pointers
        and the top-down stages, so the post-edge observation depends only on
        state.  Keeping this function input-free is what lets the agent sample
        the same input frame on both phases of the edge.
        """
        return Outputs(
            in_ready=int(self.allow_enq),
            full=int(not self.allow_enq),
            empty=int(self.enq_ptr == self.deq_ptr[0]
                      and not self.output_entries[0].valid),
            lanes=tuple(_lane_outputs(entry) for entry in self.output_entries),
            stall_reason=self._stall_reason(),
        )

    def outputs(self, inputs: Inputs) -> Outputs:
        if not isinstance(inputs, Inputs):
            raise TypeError("IBuffer model requires semantic Inputs")
        if inputs.reset:
            return reset_outputs()
        return self._registered_outputs()

    def events(self, inputs: Inputs) -> Events:
        if inputs.reset:
            return Events(0, 0, 0, 0, int(inputs.flush), 0, 0)
        return self._evaluate(inputs)["events"]

    def tick(self, inputs: Inputs) -> None:
        if not isinstance(inputs, Inputs):
            raise TypeError("IBuffer model requires semantic Inputs")
        if inputs.reset:
            self.reset_state()
            return
        result = self._evaluate(inputs)
        start = result["start"]
        fire = result["fire"]
        num_enq = result["num_enq"]
        num_out = result["num_out"]
        use_bypass = result["use_bypass"]

        if inputs.flush:
            self.enq_ptr = 0
            self.ifu_aligned = list(range(ENQUEUE_WIDTH))
            self.deq_ptr = list(range(DECODE_WIDTH))
            self.deq_bank_ptr = list(range(NUM_READ_BANK))
            self.deq_in_bank_ptr = [0] * NUM_READ_BANK
        else:
            if fire:
                old_enq = self.enq_ptr
                old_aligned = self.ifu_aligned
                # The first eight queue positions bypass the ibuf when the
                # queue was empty and decode accepted directly.
                suppressed = {(old_enq + slot) % SIZE
                              for slot in range(DECODE_WIDTH)} if use_bypass else set()
                for lane in range(ENQUEUE_WIDTH):
                    if inputs.valid >> lane & 1 and inputs.enq_enable >> lane & 1:
                        target = old_aligned[lane]
                        if target in suppressed:
                            continue
                        self.ibuf[target] = inputs.entries[lane]
                new_enq = (old_enq + num_enq) % SIZE
                base = new_enq & ~(NUM_WRITE_BANK - 1)
                self.enq_ptr = new_enq
                self.ifu_aligned = [(base + lane) % SIZE
                                    for lane in range(ENQUEUE_WIDTH)]
            bank_head = self.deq_bank_ptr[0]
            self.deq_ptr = [(value + num_out) % SIZE for value in self.deq_ptr]
            self.deq_bank_ptr = [(value + num_out) % NUM_READ_BANK
                                 for value in self.deq_bank_ptr]
            for bank in range(NUM_READ_BANK):
                valid_index = (bank - bank_head) % NUM_READ_BANK
                if num_out > valid_index:
                    self.deq_in_bank_ptr[bank] = (self.deq_in_bank_ptr[bank] + 1) \
                        % READ_BANK_SIZE

        self.output_entries = result["out_next"]
        self.first_exc_valid = result["first_valid_next"]
        self.first_exc = result["first_bits_next"]
        self.first_exc_idx = result["first_idx_next"]
        self.allow_enq = 1 if inputs.flush else result["allow_enq_next"]
        stage0 = self._override(inputs.topdown_reasons, inputs)
        stage1 = self._override(self.topdown[0], inputs)
        self.topdown = [stage0, stage1]
        self.vtype.tick(result["vg_inputs"])

    def snapshot(self) -> dict[str, object]:
        return {
            "enq_ptr": self.enq_ptr,
            "deq_ptr": self.deq_ptr[0],
            "occupancy": (self.enq_ptr - self.deq_ptr[0]) % SIZE,
            "allow_enq": self.allow_enq,
            "output_valid": [entry.valid for entry in self.output_entries],
            "first_exception_valid": self.first_exc_valid,
            "first_exception_type": EXCEPTION_NAMES[self.first_exc.exc_type],
            "vtype": self.vtype.snapshot(),
        }


# Imported late to keep the public module surface small.
from suites.frontend.ibuffer.testbenches.vtype_gen.model import Inputs as _VTypeInputs  # noqa: E402
