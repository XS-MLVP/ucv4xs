"""Only retained public wrapper inputs; no externally writable SQ feedback."""
from dataclasses import dataclass

from suites.memblock.lsq.testbenches.forward.transactions import Query
from suites.memblock.lsq.testbenches.forward.transactions import Translation
from suites.memblock.lsq.testbenches.load_queue.transactions import Bus as LoadBus
from suites.memblock.lsq.testbenches.load_queue.transactions import Bypass
from suites.memblock.lsq.testbenches.load_queue.transactions import Load
from suites.memblock.lsq.testbenches.psq.transactions import Address as PhysicalAddress
from suites.memblock.lsq.testbenches.psq.transactions import Attributes
from suites.memblock.lsq.testbenches.psq.transactions import SecondPage
from suites.memblock.lsq.testbenches.rar.transactions import Query as RarQuery
from suites.memblock.lsq.testbenches.rar.transactions import Release
from suites.memblock.lsq.testbenches.raw.transactions import FtqPtr
from suites.memblock.lsq.testbenches.raw.transactions import Query as RawQuery
from suites.memblock.lsq.testbenches.raw.transactions import SqPtr
from suites.memblock.lsq.testbenches.replay.transactions import L2Hint
from suites.memblock.lsq.testbenches.replay.transactions import Refill
from suites.memblock.lsq.testbenches.replay.transactions import StoreWakeup
from suites.memblock.lsq.testbenches.replay.transactions import TlbHint
from suites.memblock.lsq.testbenches.vlq.transactions import QueuePtr
from suites.memblock.lsq.testbenches.vlq.transactions import Redirect
from suites.memblock.lsq.testbenches.vlq.transactions import RobPtr


@dataclass(frozen=True)
class Dispatch:
    valid: bool = False
    need_alloc: int = 0
    rob: RobPtr = RobPtr()
    flows: int = 0
    load_start: QueuePtr = QueuePtr()
    store_end: SqPtr = SqPtr()


@dataclass(frozen=True)
class Address(PhysicalAddress):
    rob: RobPtr = RobPtr()
    ftq: FtqPtr = FtqPtr()
    ftq_offset: int = 0
    rvc: bool = False
    mask: int = 0
    wline: bool = False


@dataclass(frozen=True)
class Data:
    valid: bool = False
    sq: SqPtr = SqPtr()
    fu_op: int = 0
    data: int = 0


@dataclass(frozen=True)
class Bus(LoadBus):
    ack_to_load: bool = True
    response_to_load: bool = True
    outstanding: bool = False


@dataclass(frozen=True)
class Inputs:
    dispatch: tuple = (Dispatch(),) * 8
    loads: tuple = (Load(),) * 3
    rar_queries: tuple = (RarQuery(),) * 3
    raw_queries: tuple = (RawQuery(),) * 3
    rar_revoke_last: tuple = (False,) * 3
    rar_revoke_older: tuple = (False,) * 3
    raw_revoke_last: tuple = (False,) * 3
    raw_revoke_older: tuple = (False,) * 3
    replay_ready: tuple = (False,) * 3
    bypass: tuple = (Bypass(),) * 3
    addresses: tuple = (Address(),) * 2
    attributes: tuple = (Attributes(),) * 2
    data: tuple = (Data(),) * 2
    second_pages: tuple = (SecondPage(),) * 2
    queries: tuple = (Query(),) * 3
    translations: tuple = (Translation(),) * 3
    address_wakeups: tuple = (StoreWakeup(),) * 2
    data_wakeups: tuple = (StoreWakeup(),) * 2
    refills: tuple = (Refill(),) * 2
    l2_hints: tuple = (L2Hint(),) * 2
    slow_tlb: TlbHint = TlbHint()
    fast_tlb: TlbHint = TlbHint()
    pending: RobPtr = RobPtr()
    pending_next: RobPtr = RobPtr()
    release: Release = Release()
    bus: Bus = Bus()
    sbuffer_ready: tuple = (False, False)
    sbuffer_empty: bool = True
    cache_ready: bool = False
    cache_response: bool = False
    cache_denied: bool = False
    cache_corrupt: bool = False
    writeback_ready: bool = False
    redirect: Redirect = Redirect()
    reset: bool = False




# ---------------------------------------------------------------------------
# Immutable public responses of the composed LSQ wrapper.
#
# These are transaction snapshots decoded once per sampled window.  Functional
# tests never read physical pin names.  In an expectation, ``None`` means the
# field is not constrained; the ``UNSET`` sentinel means the whole channel is
# not constrained (absent channels are expressed as ``None``).
# ---------------------------------------------------------------------------
from suites.memblock.lsq.testbenches.shared.transactions import UNSET


@dataclass(frozen=True)
class BypassResponse:
    s1_valid: int | None = None
    s1_paddr: int | None = None
    s2_valid: int | None = None
    s2_data: int | None = None
    s2_derr: int | None = None
    s2_nderr: int | None = None


@dataclass(frozen=True)
class ReplaySlot:
    valid: int | None = None
    replay_queue_idx: int | None = None
    lq_idx_flag: int | None = None
    lq_idx_value: int | None = None
    checkpoint_id: int | None = None
    rob_idx_flag: int | None = None
    rob_idx_value: int | None = None
    rob_idx_former: int | None = None
    strict: int | None = None
    operation: int | None = None
    vaddr: int | None = None
    mask: int | None = None
    size: int | None = None
    mshr_id: int | None = None
    entrance: int | None = None
    instr_type: int | None = None
    sq_idx_first: int | None = None
    sq_idx_second: int | None = None
    sq_idx_value: int | None = None
    exceptions: int | None = None
    fullva: int | None = None
    nc_replay: int | None = None
    uncache_replay: int | None = None


@dataclass(frozen=True)
class SqPointerExpectation:
    first: int | None = None
    second: int | None = None
    value: int | None = None


@dataclass(frozen=True)
class Rollback:
    valid: int | None = None
    rob_value: int | None = None
    rob_flag: int | None = None
    rob_former: int | None = None
    ftq_flag: int | None = None
    ftq_value: int | None = None
    ftq_offset: int | None = None
    rvc: int | None = None
    checkpoint_id: int | None = None
    st_ftq_flag: int | None = None
    st_ftq_value: int | None = None
    st_ftq_offset: int | None = None
    st_rvc: int | None = None
    level: int | None = None
    source: str | None = None


@dataclass(frozen=True)
class MdpTrain:
    valid: int | None = None
    ftq_value: int | None = None
    ftq_offset: int | None = None
    rvc: int | None = None
    st_ftq_value: int | None = None
    st_ftq_offset: int | None = None
    st_rvc: int | None = None


@dataclass(frozen=True)
class NukeQuery:
    req_ready: int | None = None
    resp_valid: int | None = None
    nuke: int | None = None


@dataclass(frozen=True)
class UncacheRequest:
    valid: int | None = None
    cmd: int | None = None
    addr: int | None = None
    vaddr: int | None = None
    data: int | None = None
    mask: int | None = None
    ident: int | None = None
    nc: int | None = None
    memory_backed: int | None = None
    rob_value: int | None = None
    rob_flag: int | None = None
    rob_former: int | None = None


@dataclass(frozen=True)
class CacheRequest:
    valid: int | None = None
    address: int | None = None
    opcode: int | None = None


@dataclass(frozen=True)
class Writeback:
    valid: int | None = None
    rob_value: int | None = None
    rob_flag: int | None = None
    rob_former: int | None = None
    access_fault: int | None = None
    bus_error: int | None = None
    mmio: int | None = None
    ncio: int | None = None


@dataclass(frozen=True)
class ExceptionInfo:
    valid: int | None = None
    vaddr: int | None = None
    hyper: int | None = None
    access_fault: int | None = None
    bus_error: int | None = None
    rob_value: int | None = None
    rob_flag: int | None = None
    rob_former: int | None = None
    gpaddr: int | None = None
    nonleaf: int | None = None


@dataclass(frozen=True)
class SbufferWord:
    valid: int | None = None
    addr: int | None = None
    vaddr: int | None = None
    mask: int | None = None
    data: int | None = None
    wline: int | None = None


@dataclass(frozen=True)
class DeqCredit:
    valid: int | None = None
    count: int | None = None


@dataclass(frozen=True)
class ForwardResponse:
    valid: int | None = None
    forward_invalid: int | None = None
    match_invalid: int | None = None
    addr_invalid: int | None = None
    data_invalid: int | None = None
    addr_invalid_ptr: SqPtr | None = None
    data_invalid_ptr: SqPtr | None = None
    data_invalid_value: int | None = None
    forward_mask: int | None = None
    forward_data: int | None = None
    data_byte_mask: int | None = None
    mask_byte_mask: int | None = None


@dataclass(frozen=True)
class Observation:
    lq_empty: int | None = None
    # The child Replay has lqFull, but LsqWrapper does not export it. None is
    # an explicit observation gap, never an assumed deasserted full signal.
    lq_full: int | None = None
    sq_empty: int | None = None
    sq_full: int | None = None
    force_write: int | None = None
    special_mode: int | None = None
    replay_allocate: int | None = None
    rob_mmio_busy: int | None = None
    issue_ptr: SqPtr | None = None
    sq_deq_ptr: SqPtr | None = None
    lq_redirect_ptr: QueuePtr | None = None
    sq_redirect_ptr: SqPtr | None = None
    lq_recover_stall: int | None = None
    sq_recover_stall: int | None = None
    lq_dequeue: DeqCredit | None = None
    sq_dequeue: DeqCredit | None = None
    perf: tuple = ()
    replays: tuple = ()
    bypass: tuple = ()
    forward: tuple = ()
    uncache_request: object = UNSET
    # Full passive bus window for diagnostics, even when no offer is valid.
    # This is observed metadata, never an expected-response channel.
    uncache_sample: UncacheRequest | None = None
    cmo_request: object = UNSET
    cmo_response_ready: int | None = None
    mmio_stout: object = UNSET
    mmio_sample: Writeback | None = None
    ld_exception: object = UNSET
    st_exception: object = UNSET
    st_exception_sample: ExceptionInfo | None = None
    nack_rollback: Rollback | None = None
    nuke_rollback: tuple = ()
    mdp_train: MdpTrain | None = None
    sbuffer_word_0: object = UNSET
    sbuffer_word_1: object = UNSET
    rar_nuke: tuple = ()
    raw_nuke: tuple = ()
    unalign_ready: tuple = ()
