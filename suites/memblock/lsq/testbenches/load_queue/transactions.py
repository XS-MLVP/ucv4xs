from dataclasses import dataclass

from suites.memblock.lsq.testbenches.raw.transactions import Query as RawQuery
from suites.memblock.lsq.testbenches.raw.transactions import SqPtr
from suites.memblock.lsq.testbenches.raw.transactions import Store
from suites.memblock.lsq.testbenches.rar.transactions import Query as RarQuery
from suites.memblock.lsq.testbenches.rar.transactions import Release
from suites.memblock.lsq.testbenches.replay.transactions import Enqueue
from suites.memblock.lsq.testbenches.replay.transactions import L2Hint
from suites.memblock.lsq.testbenches.replay.transactions import Refill
from suites.memblock.lsq.testbenches.replay.transactions import StoreWakeup
from suites.memblock.lsq.testbenches.replay.transactions import TlbHint
from suites.memblock.lsq.testbenches.vlq.transactions import Dispatch
from suites.memblock.lsq.testbenches.vlq.transactions import QueuePtr
from suites.memblock.lsq.testbenches.vlq.transactions import Redirect
from suites.memblock.lsq.testbenches.vlq.transactions import RobPtr

EXCEPTION_BITS = (23, 21, 19, 15, 13, 7, 6, 5, 4, 3)


@dataclass(frozen=True)
class Load:
    execution: Enqueue = Enqueue()
    fullva: int = 0
    paddr: int = 0
    gpaddr: int = 0
    mmio: bool = False
    memory_backed: bool = True
    hyper: bool = False
    nonleaf: bool = False
    update_address: bool = False
    exceptions: int = 0


@dataclass(frozen=True)
class Bypass:
    valid: bool = False
    lq: QueuePtr = QueuePtr()
    nc: bool = False
    mmio: bool = False


@dataclass(frozen=True)
class Bus:
    ready: bool = False
    ack: bool = False
    mid: int = 0
    sid: int = 0
    response: bool = False
    response_id: int = 0
    data: int = 0
    error: bool = False
    nderr: bool = False


@dataclass(frozen=True)
class Inputs:
    dispatch: tuple = (Dispatch(),) * 8
    loads: tuple = (Load(),) * 3
    rar_queries: tuple = (RarQuery(),) * 3
    raw_queries: tuple = (RawQuery(),) * 3
    stores: tuple = (Store(),) * 2
    rar_revoke_last: tuple = (False,) * 3
    rar_revoke_older: tuple = (False,) * 3
    raw_revoke_last: tuple = (False,) * 3
    raw_revoke_older: tuple = (False,) * 3
    replay_ready: tuple = (False,) * 3
    address_wakeups: tuple = (StoreWakeup(),) * 2
    data_wakeups: tuple = (StoreWakeup(),) * 2
    data_writes: tuple = (StoreWakeup(),) * 2
    refills: tuple = (Refill(),) * 2
    l2_hints: tuple = (L2Hint(),) * 2
    slow_tlb: TlbHint = TlbHint()
    fast_tlb: TlbHint = TlbHint()
    address_ready: SqPtr = SqPtr()
    address_bits: int = 0
    data_ready: SqPtr = SqPtr()
    data_bits: int = 0
    dequeue: SqPtr = SqPtr()
    upper: SqPtr = SqPtr.encode(64)
    sq_empty: bool = False
    pending: RobPtr = RobPtr()
    pending_next: RobPtr = RobPtr()
    release: Release = Release()
    bypass: tuple = (Bypass(),) * 3
    bus: Bus = Bus()
    redirect: Redirect = Redirect()
    reset: bool = False


# --- Immutable public-response observations (decode stays in env/ports) ---
from dataclasses import dataclass as _dataclass


@_dataclass(frozen=True)
class ReplaySlot:
    valid: bool = False
    replay_queue_idx: int = 0
    lq_idx_flag: bool = False
    lq_idx_value: int = 0
    checkpoint_id: int = 0


@_dataclass(frozen=True)
class BypassResponse:
    s1_valid: bool = False
    s2_valid: bool = False
    paddr: int = 0
    data: int = 0
    derr: bool = False
    nderr: bool = False


@_dataclass(frozen=True)
class NukeRollback:
    valid: bool = False
    rob_idx_value: int = 0
    st_ftq_idx_value: int = 0
    checkpoint_id: int = 0


@_dataclass(frozen=True)
class NukeQuery:
    req_ready: bool = False
    resp_valid: bool = False
    nuke: bool = False


@_dataclass(frozen=True)
class Observation:
    lq_empty: bool = False
    mdp_train_valid: bool = False
    replay_allocate: bool = False
    special_mode: bool = False
    exception_valid: bool = False
    exception_vaddr: int = 0
    uncache_req_valid: bool = False
    uncache_req_addr: int = 0
    uncache_req_id: int = 0
    uncache_req_nc: bool = False
    nack_rollback: NukeRollback = NukeRollback()
    nuke_rollback: tuple[NukeRollback, NukeRollback] = (NukeRollback(), NukeRollback())
    replay: tuple[ReplaySlot, ReplaySlot, ReplaySlot] = (ReplaySlot(), ReplaySlot(), ReplaySlot())
    bypass: tuple[BypassResponse, BypassResponse, BypassResponse] = (BypassResponse(), BypassResponse(), BypassResponse())
    rar_nuke: tuple[NukeQuery, NukeQuery, NukeQuery] = (NukeQuery(), NukeQuery(), NukeQuery())
    raw_nuke: tuple[NukeQuery, NukeQuery, NukeQuery] = (NukeQuery(), NukeQuery(), NukeQuery())
