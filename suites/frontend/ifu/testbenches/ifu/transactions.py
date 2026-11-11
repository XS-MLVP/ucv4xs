"""Strict semantic input frames and immutable full-channel observations."""
from dataclasses import dataclass

from suites.frontend.ifu.testbenches.ifu.model.fetch import Inst
from suites.frontend.ifu.testbenches.ifu.model.fetch import Window
from suites.frontend.ifu.testbenches.perf_analysis.model.perf import Inputs as Reasons
from suites.frontend.ifu.testbenches.frontend_trigger.model.trigger import Inputs as TriggerInputs
from suites.frontend.ifu.testbenches.uncache_unit.transactions import BusReply

from suites.frontend.ifu.testbenches.ifu.env.input_contract import check_window_description


def unsigned(value, width, name):
    if not isinstance(value, int) or not 0 <= value < 1 << width:
        raise ValueError(f'{name} must be an unsigned{width}-bit integer')


def aligned(value, width, name):
    unsigned(value, width, name)
    if value & 1:
        raise ValueError(f'{name} must be a 2-byte aligned byte address')


def vector(value, length, width, name):
    if not isinstance(value, (list, tuple)) or len(value) != length:
        raise ValueError(f'{name} must contain exactly {length} entries')
    for entry in value:
        unsigned(entry, width, name)
    return tuple(value)


@dataclass(frozen=True)
class FetchRequest:
    """Strict interface stimulus, with no implied full-FTQ producer credit.

    Existing short/split windows intentionally characterize the IFU port domain.
    Use ProducerFetchRequest for the additional independently audited upstream
    relationships. Both go through identical ownership/monitor/checker paths.
    """
    window: Window
    physical_address: int = 0  # Full byte address, unlike legacy Window.paddr0.

    def __post_init__(self):
        if not isinstance(self.window, Window):
            raise TypeError('IFU requires a semantic Window')
        w = self.window
        aligned(self.physical_address, 48, 'physical address')
        if w.paddr0:
            raise ValueError('legacy raw paddr0 must be normalized to physical_address before submission')
        for name in ('size0', 'size1', 'split', 'spec_count', 'spec_count0'):
            unsigned(getattr(w, name), 6, name)
        if not 1 <= w.size0 <= 32 or not 0 <= w.size1 <= 31 or w.size0 + w.size1 > 32:
            raise ValueError('fetch sizes must fit the 32-halfword window')
        if w.split != w.size0 or w.block1_valid != int(w.size1 != 0):
            raise ValueError('fetch split/second-block-valid disagree with sizes')
        aligned(w.start0_pc, 51, 'block0 PC')
        if w.block1_valid:
            aligned(w.start1_pc, 51, 'block1 PC')
        for name in ('gp0', 'gp1'):
            aligned(getattr(w, name), 56, name)
        for name in ('exc0', 'exc1'):
            unsigned(getattr(w, name), 3, name)
            if getattr(w, name) > 5:
                raise ValueError('unknown IFU exception code')
        for name in ('pmp0', 'vs0', 'vs1', 'satp0', 'backend_exc0', 'taken0_valid',
                     'taken1_valid', 'block1_valid', 'half0', 'half1'):
            unsigned(getattr(w, name), 1, name)
        unsigned(w.pbmt0, 2, 'PBMT')
        unsigned(w.map, 32, 'raw compressed map')
        for name in ('ftq0', 'ftq1'):
            ptr = getattr(w, name)
            if len(ptr) != 2:
                raise ValueError('FTQ identity requires flag and value')
            unsigned(ptr[0], 1, name + '.flag')
            unsigned(ptr[1], 6, name + '.value')
        for name in ('line0', 'line1'):
            if len(getattr(w, name)) != 32:
                raise ValueError('ICache line must have 32 halfwords')
            for value in getattr(w, name):
                unsigned(value, 16, name)
        for name in ('line_offset0', 'line_offset1'):
            unsigned(getattr(w, name), 5, name)
        if not w.instructions or any(not isinstance(i, Inst) for i in w.instructions):
            raise ValueError('fetch requires a complete immutable instruction sequence')
        for inst in w.instructions:
            unsigned(inst.word, 32, 'instruction word')
            aligned(inst.pc, 51, 'instruction PC')
            for name in ('is_rvc', 'block', 'cross', 'pred_taken', 'invalid_taken', 'ftq_flag', 'ill', 'truncated'):
                unsigned(getattr(inst, name), 1, 'instruction.' + name)
            unsigned(inst.ftq_value, 6, 'instruction FTQ value')
            for name, width in (('slot', 5), ('start_offset', 5), ('end_offset', 5),
                                ('raw_data', 32), ('out_data', 32), ('branch_type', 2),
                                ('ras_action', 2), ('jump_offset', 51)):
                unsigned(getattr(inst, name), width, 'instruction.' + name)
        if w.line_offset0 != (w.start0_pc >> 1) & 31 or (w.block1_valid and
                w.line_offset1 != (w.start1_pc >> 1) & 31):
            raise ValueError('ICache line offsets must agree with byte PCs')
        total = w.size0 + w.size1
        raw = tuple(w.line0[(w.line_offset0 + i) & 31] if i < w.size0
                    else w.line1[(w.line_offset1 + i - w.size0) & 31] for i in range(total))
        if w.map != sum(int((half & 3) != 3) << i for i, half in enumerate(raw)):
            raise ValueError('raw compressed map must describe the supplied halfword data')
        check_window_description(w)

    @property
    def input_source(self):
        return 'port-characterization'


@dataclass(frozen=True)
class ProducerFetchRequest(FetchRequest):
    """DefaultConfig FTQ/ICache field relationships, not whole-core proof.

    The caller still owns the predictor/translation/PNR history outside this
    DUT. False predictions remain legal; these checks do not require the
    supplied bytes to agree with a prediction or restrict the opcode domain.
    """

    def __post_init__(self):
        super().__post_init__()
        w = self.window
        if w.pbmt0 == 3:
            raise ValueError('producer PBMT must not use the reserved encoding')
        for pc, size, taken in ((w.start0_pc, w.size0, w.taken0_valid),) + (
                ((w.start1_pc, w.size1, w.taken1_valid),) if w.block1_valid else ()):
            fallthrough_bytes = min((pc & ~31) + 64 - pc, 4096 - (pc & 0xfff))
            maximum = fallthrough_bytes // 2
            if size > maximum or (not taken and size != maximum):
                raise ValueError('producer fetch size must fit endPosition and non-taken full fall-through extent')
        if w.block1_valid:
            current = (w.ftq0[0] << 6) | w.ftq0[1]
            following = (w.ftq1[0] << 6) | w.ftq1[1]
            if following != (current + 1) % 128:
                raise ValueError('producer second fetch requires the successor FTQ flag/value')
            if w.start0_pc >> 12 != w.start1_pc >> 12:
                raise ValueError('producer dual fetch must stay on the same virtual page')
            if w.backend_exc0 or w.satp0:
                raise ValueError('producer backend exception/satp history forbids dual fetch')
        if self.physical_address & 0xfff != w.start0_pc & 0xfff:
            raise ValueError('producer physical address must preserve the translated page offset')

    @property
    def input_source(self):
        return 'producer'


@dataclass(frozen=True)
class Frame:
    request: FetchRequest | None = None
    ibuffer_ready: int = 1
    backend_redirect: int = 0
    bpu_flush: tuple[int, int] | None = None
    backend_empty: int = 1
    ibuffer_empty: int = 1
    corruption: tuple[int, int, int, int] = (0, 0, 0, 0)
    uncache_ready: int = 0
    reply: BusReply | None = None
    reply_uid: int | None = None
    reply_source: str = 'producer'
    trigger: TriggerInputs = TriggerInputs()
    reasons: Reasons = Reasons()
    cache_hits: tuple[int, int] = (0, 0)
    double_line: int = 0
    fs_is_off: int = 0
    reset: int = 0

    def __post_init__(self):
        if self.request is not None and not isinstance(self.request, FetchRequest):
            raise TypeError('frame.request must be a FetchRequest')
        for name in ('ibuffer_ready', 'backend_redirect', 'backend_empty', 'ibuffer_empty',
                     'uncache_ready', 'double_line', 'fs_is_off', 'reset'):
            unsigned(getattr(self, name), 1, name)
        for name, length in (('corruption', 4), ('cache_hits', 2)):
            values = getattr(self, name)
            if not isinstance(values, (list, tuple)) or len(values) != length:
                raise ValueError(f'{name} must contain exactly{length} entries')
            for value in values:
                unsigned(value, 1, name)
            object.__setattr__(self, name, tuple(values))
        if self.bpu_flush is not None:
            if not isinstance(self.bpu_flush, (list, tuple)) or len(self.bpu_flush) != 2:
                raise ValueError('BPU flush requires an FTQ flag/value')
            unsigned(self.bpu_flush[0], 1, 'flush flag')
            unsigned(self.bpu_flush[1], 6, 'flush value')
            object.__setattr__(self, 'bpu_flush', tuple(self.bpu_flush))
        if not isinstance(self.trigger, TriggerInputs) or not isinstance(self.reasons, Reasons):
            raise TypeError('trigger/reasons must use their semantic transaction types')
        if self.trigger.pcs != TriggerInputs().pcs:
            raise ValueError('IFU trigger PCs are owned by the accepted fetch, not an external input')
        if self.reasons.ifu_wb_redirect:
            raise ValueError('IFU writeback reason is owned by the internal redirect, not an external input')
        if self.reply is not None and (not isinstance(self.reply, BusReply) or type(self.reply_uid) is not int or self.reply_uid < 1):
            raise ValueError('bus reply requires a semantic BusReply and positive input-established UID')
        if self.reply is None and self.reply_uid is not None:
            raise ValueError('reply UID without a reply')
        if self.reply_source not in ('producer', 'port-characterization'):
            raise ValueError('unknown reply source')
        if self.reply is None and self.reply_source != 'producer':
            raise ValueError('reply source requires a reply')


@dataclass(frozen=True)
class Enqueue:
    valid: int
    enq: int
    instrs: tuple[int, ...]
    is_rvc: tuple[int, ...]
    foldpc: tuple[int, ...]
    ftq: tuple[tuple[int, int], ...]
    end_off: tuple[int, ...]
    pred: tuple[int, ...]
    prev_count: int
    exception_type: int
    exception_mask: int
    exception_cross: int
    is_backend_exception: int
    has_satp_flush: int
    triggered: tuple[int, ...]

    def __post_init__(self):
        for name, width in (('valid', 36), ('enq', 36), ('prev_count', 6), ('exception_type', 3),
                ('exception_mask', 36), ('exception_cross', 1), ('is_backend_exception', 1), ('has_satp_flush', 1)):
            unsigned(getattr(self, name), width, name)
        for name, width in (('instrs', 32), ('is_rvc', 1), ('foldpc', 10), ('end_off', 5), ('pred', 1), ('triggered', 4)):
            object.__setattr__(self, name, vector(getattr(self, name), 36, width, name))
        if not isinstance(self.ftq, (list, tuple)) or len(self.ftq) != 36:
            raise ValueError('enqueue FTQ vector must contain exactly 36 pointers')
        pointers = []
        for ptr in self.ftq:
            if not isinstance(ptr, (list, tuple)) or len(ptr) != 2:
                raise ValueError('FTQ pointer must contain flag/value')
            unsigned(ptr[0], 1, 'FTQ flag')
            unsigned(ptr[1], 6, 'FTQ value')
            pointers.append(tuple(ptr))
        object.__setattr__(self, 'ftq', tuple(pointers))


@dataclass(frozen=True)
class Redirect:
    ftq: tuple[int, int]
    can_train: int
    pc: int
    taken: int
    offset: int
    is_rvc: int
    branch_type: int
    ras_action: int
    target: int

    def __post_init__(self):
        if not isinstance(self.ftq, (list, tuple)) or len(self.ftq) != 2:
            raise ValueError('redirect FTQ pointer requires flag/value')
        unsigned(self.ftq[0], 1, 'redirect FTQ flag')
        unsigned(self.ftq[1], 6, 'redirect FTQ value')
        object.__setattr__(self, 'ftq', tuple(self.ftq))
        for name in ('can_train', 'taken', 'is_rvc'):
            unsigned(getattr(self, name), 1, name)
        for name, width in (('pc', 51), ('target', 51)):
            aligned(getattr(self, name), width, name)
        unsigned(self.offset, 5, 'redirect offset')
        unsigned(self.branch_type, 2, 'branch type')
        unsigned(self.ras_action, 2, 'RAS action')


@dataclass(frozen=True)
class BusRequest:
    address: int
    main_memory: int
    noncacheable: int

    def __post_init__(self):
        aligned(self.address, 48, 'bus address')
        unsigned(self.main_memory, 1, 'main memory')
        unsigned(self.noncacheable, 1, 'noncacheable')


@dataclass(frozen=True)
class GpaWrite:
    ftq_index: int
    address: int
    for_vs: int

    def __post_init__(self):
        unsigned(self.ftq_index, 6, 'GPA FTQ index')
        aligned(self.address, 56, 'GPA address')
        unsigned(self.for_vs, 1, 'GPA VS-nonleaf flag')


@dataclass(frozen=True)
class Snapshot:
    fetch_ready: int
    beat: Enqueue | None
    redirect: Redirect | None
    bus: BusRequest | None
    gpa: GpaWrite | None
    reasons: int
    performance: tuple[int, ...]

    def __post_init__(self):
        unsigned(self.fetch_ready, 1, 'fetch_ready')
        unsigned(self.reasons, 76, 'topdown reasons')
        for name, cls in (('beat', Enqueue), ('redirect', Redirect), ('bus', BusRequest), ('gpa', GpaWrite)):
            if getattr(self, name) is not None and not isinstance(getattr(self, name), cls):
                raise TypeError(f'snapshot.{name} must be a complete immutable {cls.__name__}')
        object.__setattr__(self, 'performance', vector(self.performance, 13, 6, 'performance'))


@dataclass(frozen=True)
class CheckedCycle:
    sequence: int
    before_tick: int
    after_tick: int
    before: Snapshot
    after: Snapshot
    req_fire_uid: int | None
    accepted_uid: int | None
    beat_uid: int | None
    redirect_uid: int | None
    offered_uid: int | None = None
    bus_fire_uid: int | None = None


@dataclass(frozen=True)
class FetchResult:
    uid: int
    beat: Enqueue | None
    redirect: Redirect | None
    gpa: GpaWrite | None = None
    bus: BusRequest | None = None
    resend: int = 0
    peer_source: str | None = None
    input_source: str = 'port-characterization'


@dataclass(frozen=True)
class Interface:
    input_count: int = 80
    output_count: int = 405
    request_pc_bits: int = 51  # Byte-address semantic width, implicit bit0.
    redirect_pc_bits: int = 51  # full GuardedPc; R-08 closed by b716aade.
    redirect_target_bits: int = 51
    padding_pred_taken: int = 0
