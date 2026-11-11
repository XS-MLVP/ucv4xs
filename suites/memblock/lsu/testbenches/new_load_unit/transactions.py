"""Load transactions and immutable stage snapshots for NewLoadUnit.

A test describes a load by its architectural request (address, operation, ROB /
LQ / SQ identity, register destination and prefetch flags) and by the protocol
responses it receives in a given cycle.  It never has to know the generated
port spelling: ``env.stimulus`` lowers :class:`CycleInput` into the driver
encoding and ``env.monitor`` decodes the public outputs into the frozen stage
observations defined here.

Identity is carried by value, not inferred from a later observation.  The same
:class:`RobTag` instance is used to build the request and is compared with the
writeback afterwards; a response is never searched for by data equality.

Contracts:
``docs/spec/design/contracts/new-load-unit.md`` §2/§3/§5/§6 and the per-stage
contracts ``load-s0.md`` … ``load-s3.md``.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import IntEnum

# Encodings named by the load contract; these are operation codes, not pins.
LD = 0x06
LW = 0x04
LH = 0x02
LB = 0x00
SW_PREFETCH = 0x03
HW_PREFETCH_I = 0x01


def _uint(value, width: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < (1 << width):
        raise ValueError(f"{name} must be an unsigned {width}-bit integer, got {value!r}")


def _flag(value, name: str) -> None:
    if isinstance(value, bool):
        return
    if not isinstance(value, int) or value not in (0, 1):
        raise ValueError(f"{name} must be 0 or 1, got {value!r}")


def _expect(value, cls, name: str) -> None:
    if not isinstance(value, cls):
        raise TypeError(
            f"{name} must be a {cls.__name__}, got {type(value).__name__}")


# --------------------------------------------------------------------- identity
@dataclass(frozen=True)
class RobTag:
    """ROB identity: value plus wrap flag plus isFormer disambiguation."""

    value: int = 0
    flag: int = 0
    is_former: int = 0

    def __post_init__(self) -> None:
        _uint(self.value, 8, "rob.value")
        _flag(self.flag, "rob.flag")
        _flag(self.is_former, "rob.is_former")


@dataclass(frozen=True)
class SqTag:
    """Store-queue identity.  ``second_flag`` marks a 32-entry wrap."""

    value: int = 0
    first_flag: int = 0
    second_flag: int = 0

    def __post_init__(self) -> None:
        _uint(self.value, 6, "sq.value")
        _flag(self.first_flag, "sq.first_flag")
        _flag(self.second_flag, "sq.second_flag")


@dataclass(frozen=True)
class LqTag:
    value: int = 0
    flag: int = 0

    def __post_init__(self) -> None:
        _uint(self.value, 7, "lq.value")
        _flag(self.flag, "lq.flag")


@dataclass(frozen=True)
class FtqPtr:
    value: int = 0
    flag: int = 0

    def __post_init__(self) -> None:
        _uint(self.value, 6, "ftq.value")
        _flag(self.flag, "ftq.flag")


# -------------------------------------------------------------- requests / inputs
@dataclass(frozen=True)
class LoadIssue:
    """One ``ldin`` beat: the load the front end wants this unit to execute."""

    address: int
    rob: RobTag
    pdest: int = 0x35
    lq_idx: int = 3
    sq_idx: int = 2
    fu_op: int = LD
    rf_wen: bool = True
    fp_wen: bool = False
    vec_wen: bool = False
    v0_wen: bool = False
    store_set_hit: bool = False
    wait_sq: SqTag | None = None

    def __post_init__(self) -> None:
        _uint(self.address, 64, "load.address")
        _uint(self.pdest, 8, "load.pdest")
        _uint(self.lq_idx, 7, "load.lq_idx")
        _uint(self.sq_idx, 6, "load.sq_idx")
        _uint(self.fu_op, 12, "load.fu_op")
        for name in ("rf_wen", "fp_wen", "vec_wen", "v0_wen", "store_set_hit"):
            _flag(getattr(self, name), f"load.{name}")
        _expect(self.rob, RobTag, "load.rob")
        if self.wait_sq is not None:
            _expect(self.wait_sq, SqTag, "load.wait_sq")


@dataclass(frozen=True)
class Translation:
    """TLB response consumed by S1.  ``paddr_1`` is the next-line pair."""

    paddr: int
    fullva: int
    paddr_1: int | None = None
    miss: bool = False
    pbmt: int = 0
    page_fault: bool = False

    def __post_init__(self) -> None:
        _uint(self.paddr, 48, "translation.paddr")
        _uint(self.fullva, 64, "translation.fullva")
        _uint(self.pbmt, 2, "translation.pbmt")
        _flag(self.miss, "translation.miss")
        _flag(self.page_fault, "translation.page_fault")
        if self.paddr_1 is None:
            object.__setattr__(self, "paddr_1", self.paddr + 0x800)
        _uint(self.paddr_1, 48, "translation.paddr_1")

    @classmethod
    def hit(cls, paddr: int, fullva: int, **options) -> "Translation":
        return cls(paddr=paddr, fullva=fullva, **options)


@dataclass(frozen=True)
class ReplayRequest:
    """A replay-queue offer entering S0 through the replay lane."""

    vaddr: int
    fullva: int
    entrance: int = 0x02
    size: int = 3
    mask: int = 0x00FF
    lq_idx: int = 0
    lq_idx_flag: int = 0
    pdest: int = 0
    rf_wen: bool = False
    fu_op: int = 0
    uncache_replay: bool = False
    nc_replay: bool = False

    def __post_init__(self) -> None:
        _uint(self.vaddr, 50, "replay.vaddr")
        _uint(self.fullva, 64, "replay.fullva")
        _uint(self.entrance, 8, "replay.entrance")
        _uint(self.size, 3, "replay.size")
        _uint(self.mask, 16, "replay.mask")
        _uint(self.lq_idx, 7, "replay.lq_idx")
        _flag(self.lq_idx_flag, "replay.lq_idx_flag")
        _uint(self.pdest, 8, "replay.pdest")
        _uint(self.fu_op, 12, "replay.fu_op")
        for name in ("rf_wen", "uncache_replay", "nc_replay"):
            _flag(getattr(self, name), f"replay.{name}")


@dataclass(frozen=True)
class DcacheControls:
    ready: bool = True
    bank_conflict: bool = False
    rr_conflict: bool = False
    mshr_nack: bool = False

    def __post_init__(self) -> None:
        for name in ("ready", "bank_conflict", "rr_conflict", "mshr_nack"):
            _flag(getattr(self, name), f"dcache.{name}")


@dataclass(frozen=True)
class DcacheRead:
    data: int = 0
    miss: bool = False
    mshr_id: int = 0
    meta_prefetch: int = 0
    handled: bool = False

    def __post_init__(self) -> None:
        _uint(self.data, 128, "dcache_read.data")
        _uint(self.mshr_id, 4, "dcache_read.mshr_id")
        _uint(self.meta_prefetch, 3, "dcache_read.meta_prefetch")
        _flag(self.miss, "dcache_read.miss")
        _flag(self.handled, "dcache_read.handled")


@dataclass(frozen=True)
class Redirect:
    rob: RobTag = RobTag()
    level: int = 0
    valid: bool = False

    def __post_init__(self) -> None:
        _expect(self.rob, RobTag, "redirect.rob")
        _flag(self.level, "redirect.level")
        _flag(self.valid, "redirect.valid")


@dataclass(frozen=True)
class NukeQuery:
    """Store-load nuke query (two slots at the parent)."""

    rob: RobTag = RobTag()
    sq: SqTag = SqTag()
    paddr: int = 0
    mask: int = 0
    match_type: int = 0
    valid: bool = False

    def __post_init__(self) -> None:
        _expect(self.rob, RobTag, "nuke.rob")
        _expect(self.sq, SqTag, "nuke.sq")
        _uint(self.paddr, 48, "nuke.paddr")
        _uint(self.mask, 16, "nuke.mask")
        _uint(self.match_type, 2, "nuke.match_type")
        _flag(self.valid, "nuke.valid")


@dataclass(frozen=True)
class TriggerSlot:
    """One CSR trigger slot in its frozen, contract-width form.

    Widths match the generated `csrTrigger_tdataVec_i_*` ports (matchType 2,
    select/timing/chain/store 1, action 4, tdata2 64).  The value is copied to
    the driver-compatible shared configuration only while encoding, so callers
    cannot mutate a recorded cycle through a shared mutable slot object.
    """

    match_type: int = 0
    select: int = 0
    timing: int = 0
    action: int = 1
    chain: int = 0
    store: int = 1
    tdata2: int = 0

    def __post_init__(self) -> None:
        _uint(self.match_type, 2, "trigger.match_type")
        _uint(self.action, 4, "trigger.action")
        _uint(self.tdata2, 64, "trigger.tdata2")
        for name in ("select", "timing", "chain", "store"):
            _flag(getattr(self, name), f"trigger.{name}")


@dataclass(frozen=True)
class TriggerSettings:
    """CSR trigger slots as seen by the load unit; four slots always exist.

    Empty containers are the idle default: four default :class:`TriggerSlot`
    values and four disabled enables.  Non-empty containers must contain
    exactly four slots/bits; each value is copied into a tuple so later
    mutation of the caller's list cannot change this transaction.
    """

    configs: tuple = ()
    enables: tuple = ()
    debug_mode: bool = False
    can_raise_bp_exp: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.configs, (tuple, list)):
            raise TypeError("trigger.configs must be a tuple or list")
        if not isinstance(self.enables, (tuple, list)):
            raise TypeError("trigger.enables must be a tuple or list")
        configs = tuple(self.configs)
        if not configs:
            configs = (TriggerSlot(),) * 4
        elif len(configs) != 4:
            raise ValueError("trigger settings require four config slots")
        for index, config in enumerate(configs):
            _expect(config, TriggerSlot, f"trigger.configs[{index}]")
        enables = tuple(self.enables)
        if not enables:
            enables = (0, 0, 0, 0)
        elif len(enables) != 4:
            raise ValueError("trigger settings require four enable bits")
        for index, bit in enumerate(enables):
            _flag(bit, f"trigger.enables[{index}]")
        _flag(self.debug_mode, "trigger.debug_mode")
        _flag(self.can_raise_bp_exp, "trigger.can_raise_bp_exp")
        object.__setattr__(self, "configs", configs)
        object.__setattr__(self, "enables", tuple(int(bit) for bit in enables))


@dataclass(frozen=True)
class BypassStage1:
    valid: bool = False
    paddr: int = 0

    def __post_init__(self) -> None:
        _uint(self.paddr, 48, "bypass1.paddr")
        _flag(self.valid, "bypass1.valid")


@dataclass(frozen=True)
class BypassStage2:
    valid: bool = False
    data: int = 0
    nderr: bool = False
    derr: bool = False

    def __post_init__(self) -> None:
        _uint(self.data, 128, "bypass2.data")
        for name in ("valid", "nderr", "derr"):
            _flag(getattr(self, name), f"bypass2.{name}")


@dataclass(frozen=True)
class RarResponse:
    valid: bool = False
    nuke: bool = False

    def __post_init__(self) -> None:
        _flag(self.valid, "rar.valid")
        _flag(self.nuke, "rar.nuke")


@dataclass(frozen=True)
class SqResponse:
    """SQ forward response; only the data-invalid half is used by these tests."""

    valid: bool = False
    data_invalid: SqTag | None = None

    def __post_init__(self) -> None:
        _flag(self.valid, "sq.valid")
        if self.data_invalid is not None:
            _expect(self.data_invalid, SqTag, "sq.data_invalid")


# ---------------------------------------------------------------- cycle input
@dataclass(frozen=True)
class CycleInput:
    """Everything the environment drives in one cycle.

    Fields are optional protocol transactions; absent means the corresponding
    source is idle for that cycle.  ``replace``-based helpers keep the object
    frozen so a sequence cannot be mutated after it was recorded.
    """

    load: LoadIssue | None = None
    replay: ReplayRequest | None = None
    translation: Translation | None = None
    dcache: DcacheControls = DcacheControls()
    dcache_read: DcacheRead = DcacheRead()
    redirect: Redirect = Redirect()
    nuke: tuple = (NukeQuery(), NukeQuery())
    bypass1: BypassStage1 = BypassStage1()
    bypass2: BypassStage2 = BypassStage2()
    trigger: TriggerSettings | None = None
    rar: RarResponse = RarResponse()
    rar_ready: bool = True
    raw_ready: bool = True
    ldld_check: bool = False
    sq: SqResponse = SqResponse()
    rr_grant: bool = False

    def __post_init__(self) -> None:
        if self.load is not None:
            _expect(self.load, LoadIssue, "cycle.load")
        if self.replay is not None:
            _expect(self.replay, ReplayRequest, "cycle.replay")
        if self.translation is not None:
            _expect(self.translation, Translation, "cycle.translation")
        _expect(self.dcache, DcacheControls, "cycle.dcache")
        _expect(self.dcache_read, DcacheRead, "cycle.dcache_read")
        _expect(self.redirect, Redirect, "cycle.redirect")
        _expect(self.bypass1, BypassStage1, "cycle.bypass1")
        _expect(self.bypass2, BypassStage2, "cycle.bypass2")
        _expect(self.rar, RarResponse, "cycle.rar")
        _expect(self.sq, SqResponse, "cycle.sq")
        if self.trigger is not None:
            _expect(self.trigger, TriggerSettings, "cycle.trigger")
        if not isinstance(self.nuke, (tuple, list)):
            raise TypeError("cycle.nuke must be a tuple or list")
        nuke = tuple(self.nuke)
        if len(nuke) != 2:
            raise ValueError("exactly two nuke query slots exist")
        for index, query in enumerate(nuke):
            _expect(query, NukeQuery, f"cycle.nuke[{index}]")
        for name in ("rar_ready", "raw_ready", "ldld_check", "rr_grant"):
            _flag(getattr(self, name), f"cycle.{name}")
        object.__setattr__(self, "nuke", nuke)

    @classmethod
    def idle(cls) -> "CycleInput":
        return cls()

    def issue(self, load: LoadIssue) -> "CycleInput":
        return replace(self, load=load)

    def replaying(self, replay: ReplayRequest) -> "CycleInput":
        return replace(self, replay=replay)

    def translated(self, translation: Translation) -> "CycleInput":
        return replace(self, translation=translation)

    def with_dcache(self, *, ready: bool = True, bank_conflict: bool = False,
                    rr_conflict: bool = False, mshr_nack: bool = False) -> "CycleInput":
        return replace(self, dcache=DcacheControls(
            ready=ready, bank_conflict=bank_conflict,
            rr_conflict=rr_conflict, mshr_nack=mshr_nack))

    def with_dcache_read(self, read: DcacheRead) -> "CycleInput":
        return replace(self, dcache_read=read)

    def redirecting(self, redirect: Redirect) -> "CycleInput":
        return replace(self, redirect=redirect)

    def with_nuke(self, slot: int, query: NukeQuery) -> "CycleInput":
        if slot not in (0, 1):
            raise ValueError(f"nuke slot must be 0 or 1, got {slot!r}")
        slots = list(self.nuke)
        slots[slot] = query
        return replace(self, nuke=tuple(slots))

    def with_bypass1(self, *, valid: bool, paddr: int = 0) -> "CycleInput":
        return replace(self, bypass1=BypassStage1(valid=valid, paddr=paddr))

    def with_bypass2(self, *, valid: bool, data: int = 0,
                     nderr: bool = False, derr: bool = False) -> "CycleInput":
        return replace(self, bypass2=BypassStage2(
            valid=valid, data=data, nderr=nderr, derr=derr))

    def with_trigger(self, settings: TriggerSettings) -> "CycleInput":
        return replace(self, trigger=settings)

    def with_rar(self, response: RarResponse, *, ready: bool | None = None) -> "CycleInput":
        return replace(self, rar=response,
                       rar_ready=self.rar_ready if ready is None else ready)

    def without_rar_ready(self) -> "CycleInput":
        return replace(self, rar_ready=False)

    def without_raw_ready(self) -> "CycleInput":
        return replace(self, raw_ready=False)

    def with_ldld_check(self, enabled: bool = True) -> "CycleInput":
        return replace(self, ldld_check=enabled)

    def with_sq_data_invalid(self, *, first_flag: int = 0, second_flag: int = 0,
                             value: int = 0) -> "CycleInput":
        return replace(self, sq=SqResponse(
            valid=True, data_invalid=SqTag(value=value, first_flag=first_flag,
                                           second_flag=second_flag)))

    def with_rr_grant(self, granted: bool = True) -> "CycleInput":
        return replace(self, rr_grant=granted)


# ------------------------------------------------------------ replay cause set
class ReplayCause(IntEnum):
    """``rep_info.cause_*`` bits.  Names follow the S2 contract table."""

    UNCACHE_FIRST_ACCESS = 0
    FORWARD_INVALID = 1
    STORE_SET_ADDRESS_INVALID = 2
    TLB_MISS = 3
    SQ_DATA_INVALID = 4
    MSHR_NACK = 5
    DCACHE_MISS = 6
    BANK_CONFLICT = 8
    RAR_NACK = 9
    RAW_NACK = 10
    NUKE = 11


@dataclass(frozen=True)
class ReplayCauses:
    """One-hot (in legal cases) collection of replay reasons."""

    causes: frozenset = frozenset()

    def __bool__(self) -> bool:
        return bool(self.causes)

    def has(self, cause) -> bool:
        return int(cause) in self.causes

    def codes(self) -> tuple:
        return tuple(sorted(int(cause) for cause in self.causes))

    def __iter__(self):
        return iter(sorted(self.causes, key=int))


# --------------------------------------------------------------- observations
@dataclass(frozen=True)
class ExceptionBits:
    bits: frozenset = frozenset()

    def has(self, code: int) -> bool:
        return code in self.bits

    @property
    def breakpoint(self) -> bool:
        return self.has(3)

    @property
    def load_address_misaligned(self) -> bool:
        return self.has(4)

    @property
    def load_access_fault(self) -> bool:
        return self.has(5)

    @property
    def load_page_fault(self) -> bool:
        return self.has(13)

    def codes(self) -> tuple:
        return tuple(sorted(self.bits))


@dataclass(frozen=True)
class TlbRequest:
    valid: int = 0
    vaddr: int = 0
    fullva: int = 0
    check_fullva: int = 0
    hyperinst: int = 0
    hlvx: int = 0
    kill: int = 0
    is_prefetch: int = 0
    no_translate: int = 0
    debug_rob: RobTag = RobTag()


@dataclass(frozen=True)
class DcacheRequest:
    valid: int = 0
    cmd: int = 0
    vaddr: int = 0
    vaddr_dup: int = 0
    mask: int = 0
    instr_type: int = 0
    lq: LqTag = LqTag()
    is_128: int = 0


@dataclass(frozen=True)
class Wakeup:
    valid: int = 0
    rf_wen: int = 0
    fp_wen: int = 0
    pdest: int = 0


@dataclass(frozen=True)
class StoreForwardRequest:
    valid: int = 0
    vaddr: int = 0
    sq: SqTag = SqTag()
    size: int = 0
    load_wait_bit: int = 0
    load_wait_strict: int = 0
    wait_sq: SqTag = SqTag()


@dataclass(frozen=True)
class SimpleForwardRequest:
    valid: int = 0
    vaddr: int = 0


@dataclass(frozen=True)
class MshrForwardRequest:
    valid: int = 0
    mshr_id: int = 0


@dataclass(frozen=True)
class TldForwardRequest:
    valid: int = 0
    mshr_id: int = 0
    s1_paddr: int = 0


@dataclass(frozen=True)
class UncacheBypassRequest:
    valid: int = 0
    lq: LqTag = LqTag()
    replay_is_nc: int = 0
    replay_is_mmio: int = 0


@dataclass(frozen=True)
class Stage0Observation:
    ldin_ready: int = 0
    replay_ready: int = 0
    tlb: TlbRequest = TlbRequest()
    dcache: DcacheRequest = DcacheRequest()
    wakeup: Wakeup = Wakeup()
    store_forward: StoreForwardRequest = StoreForwardRequest()
    sbuffer_forward: SimpleForwardRequest = SimpleForwardRequest()
    uncache_forward: SimpleForwardRequest = SimpleForwardRequest()
    mshr_forward: MshrForwardRequest = MshrForwardRequest()
    tld_forward: tuple = ()
    uncache_bypass: UncacheBypassRequest = UncacheBypassRequest()


@dataclass(frozen=True)
class Stage1Observation:
    prefetch_train_hint: int = 0
    sw_prefetch: SimpleForwardRequest = SimpleForwardRequest()
    tlb_kill: int = 0
    tlb_pmp_addr: int = 0
    dcache_kill: int = 0
    dcache_s1_paddr_lsu: int = 0
    dcache_s1_paddr_dcache: int = 0
    store_forward_paddr: int = 0
    store_forward_kill: int = 0
    sbuffer_forward_paddr: int = 0
    sbuffer_forward_kill: int = 0
    uncache_forward_paddr: int = 0
    uncache_forward_kill: int = 0
    mshr_forward_paddr: int = 0


@dataclass(frozen=True)
class RarNukeQuery:
    valid: int = 0
    rob: RobTag = RobTag()
    paddr: int = 0
    lq: LqTag = LqTag()
    data_valid: int = 0
    nc: int = 0


@dataclass(frozen=True)
class RawNukeQuery:
    valid: int = 0
    rob: RobTag = RobTag()
    paddr: int = 0
    sq: SqTag = SqTag()
    data_valid: int = 0
    mask: int = 0
    is_rvc: int = 0
    ftq: FtqPtr = FtqPtr()
    ftq_offset: int = 0
    debug_id: int = 0


@dataclass(frozen=True)
class Stage2Observation:
    rar_nuke_query: RarNukeQuery = RarNukeQuery()
    raw_nuke_query: RawNukeQuery = RawNukeQuery()
    rr_bank_conflict_candidate: int = 0
    dcache_kill: int = 0
    prefetch_train_hint: int = 0


@dataclass(frozen=True)
class RobWriteback:
    valid: int = 0
    rob: RobTag = RobTag()
    exceptions: ExceptionBits = ExceptionBits()
    trigger: int = 0
    is_mmio: int = 0
    is_nc: int = 0


@dataclass(frozen=True)
class VectorRobWriteback:
    valid: int = 0
    rob: RobTag = RobTag()
    exceptions: ExceptionBits = ExceptionBits()
    trigger: int = 0


@dataclass(frozen=True)
class IntRfWrite:
    valid: int = 0
    pdest: int = 0
    data: int = 0


@dataclass(frozen=True)
class FpRfWrite:
    valid: int = 0
    pdest: int = 0
    data: int = 0


@dataclass(frozen=True)
class VectorRfWrite:
    valid: int = 0
    data: int = 0


@dataclass(frozen=True)
class VectorWakeup:
    wen: int = 0
    pdest: int = 0


@dataclass(frozen=True)
class LqWrite:
    valid: int = 0
    paddr: int = 0
    vaddr: int = 0
    fullva: int = 0
    gpaddr: int = 0
    mask: int = 0
    aligned_type: int = 0
    is_vec: int = 0
    is_for_vs_non_leaf_pte: int = 0
    is_hyper: int = 0
    mmio: int = 0
    nc: int = 0
    mem_back_type_mm: int = 0
    sched_index: int = 0
    special_mode_request: int = 0
    special_mode_eligible: int = 0
    tlb_id: int = 0
    tlb_full: int = 0
    mshr_id: int = 0
    handled_by_mshr: int = 0
    need_rep: int = 0
    last_beat: int = 0
    rep_from_unalign_head: int = 0
    update_addr_valid: int = 0
    is_load_replay: int = 0
    replay_causes: ReplayCauses = ReplayCauses()
    uop_rob: RobTag = RobTag()
    uop_lq: LqTag = LqTag()
    uop_sq: SqTag = SqTag()
    uop_fu_op: int = 0
    uop_ftq: FtqPtr = FtqPtr()
    uop_ftq_offset: int = 0
    uop_is_rvc: int = 0
    uop_load_wait_bit: int = 0
    uop_load_wait_strict: int = 0
    uop_debug_id: int = 0
    uop_pdest: int = 0
    uop_rf_wen: int = 0
    uop_fp_wen: int = 0
    uop_vec_wen: int = 0
    uop_v0_wen: int = 0
    uop_store_set_hit: int = 0
    uop_wait_sq: SqTag = SqTag()
    addr_invalid_sq: SqTag = SqTag()
    data_invalid_sq: SqTag = SqTag()
    exceptions: ExceptionBits = ExceptionBits()

    def replay_cause(self, cause: ReplayCause) -> bool:
        return self.replay_causes.has(cause)


@dataclass(frozen=True)
class Revoke:
    last_cycle: int = 0
    last_last_cycle: int = 0


@dataclass(frozen=True)
class Rollback:
    valid: int = 0
    rob: RobTag = RobTag()
    level: int = 0
    ftq: FtqPtr = FtqPtr()
    ftq_offset: int = 0
    is_rvc: int = 0
    debug_id: int = 0


@dataclass(frozen=True)
class ExceptionInfo:
    valid: int = 0
    rob: RobTag = RobTag()
    vaddr: int = 0
    gpaddr: int = 0
    va_need_ext: int = 0
    is_hyper: int = 0
    is_for_vs_non_leaf_pte: int = 0
    exceptions: ExceptionBits = ExceptionBits()


@dataclass(frozen=True)
class Stage3Observation:
    ldout: RobWriteback = RobWriteback()
    vldout: VectorRobWriteback = VectorRobWriteback()
    vldout_pdest: int = 0
    int_rf: IntRfWrite = IntRfWrite()
    fp_rf: FpRfWrite = FpRfWrite()
    vec_rf: VectorRfWrite = VectorRfWrite()
    v0_rf: VectorRfWrite = VectorRfWrite()
    vector_wakeup: VectorWakeup = VectorWakeup()
    lq: LqWrite = LqWrite()
    rar_revoke: Revoke = Revoke()
    raw_revoke: Revoke = Revoke()
    rollback: Rollback = Rollback()
    exception_info: ExceptionInfo = ExceptionInfo()
    cancel: int = 0


@dataclass(frozen=True)
class PrefetchTrain:
    valid: int = 0
    rob: RobTag = RobTag()
    vaddr: int = 0
    paddr: int = 0
    miss: int = 0
    meta_source: int = 0
    is_first_issue: int = 0
    is_hw_prefetch: int = 0


@dataclass(frozen=True)
class PerfCounters:
    """The eight parent-level counters after their two-cycle delay."""

    values: tuple = (0, 0, 0, 0, 0, 0, 0, 0)

    def __post_init__(self) -> None:
        if len(self.values) != 8:
            raise ValueError("NewLoadUnit exposes eight performance counters")

    @property
    def issue_count(self) -> int:
        """perf_0: S0 issue beats (load-s0 contract)."""
        return self.values[0]

    def __getitem__(self, index: int) -> int:
        return self.values[index]


@dataclass(frozen=True)
class LoadPipelineSnapshot:
    """One sampled cycle of the whole load pipeline, grouped by stage."""

    cycle: int = 0
    s0: Stage0Observation = Stage0Observation()
    s1: Stage1Observation = Stage1Observation()
    s2: Stage2Observation = Stage2Observation()
    s3: Stage3Observation = Stage3Observation()
    prefetch_train: PrefetchTrain = PrefetchTrain()
    perf: PerfCounters = PerfCounters()
