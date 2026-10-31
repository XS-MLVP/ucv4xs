from dataclasses import dataclass

from suites.memblock.lsq.raw.types import Query as RawQuery, SqPtr, Store
from suites.memblock.lsq.rar.types import Query as RarQuery, Release
from suites.memblock.lsq.replay.types import Enqueue, L2Hint, Refill, StoreWakeup, TlbHint
from suites.memblock.lsq.vlq.types import Dispatch, QueuePtr, Redirect, RobPtr

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
