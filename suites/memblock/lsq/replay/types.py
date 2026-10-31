"""Architectural identities and producer obligations, not RTL register mirrors."""
from dataclasses import dataclass
from enum import IntEnum

from suites.memblock.lsq.raw.types import FtqPtr, SqPtr
from suites.memblock.lsq.vlq.types import QueuePtr, Redirect, RobPtr

SOURCE_EXCEPTION_BITS = (23, 19, 15, 7, 6)


class Cause(IntEnum):
    UNCACHE = 0
    STORE_MULTI_MATCH = 1
    ADDRESS_DEPENDENCE = 2
    TLB_MISS = 3
    FORWARD_FAILURE = 4
    CACHE_REPLAY = 5
    CACHE_MISS = 6
    WAY_PREDICTION = 7
    BANK_CONFLICT = 8
    RAR_CAPACITY = 9
    RAW_CAPACITY = 10
    VIOLATION = 11
    RESERVED_MISALIGN_FULL = 12


@dataclass(frozen=True)
class Uop:
    rob: RobPtr = RobPtr()
    lq: QueuePtr = QueuePtr()
    sq: SqPtr = SqPtr()
    ftq: FtqPtr = FtqPtr()
    offset: int = 0
    rvc: bool = False
    checkpoint: int = 0
    operation: int = 3
    integer_write: bool = True
    fp_write: bool = False
    vector_write: bool = False
    v0_write: bool = False
    destination: int = 1
    store_set_hit: bool = False
    wait_sq: SqPtr = SqPtr()
    load_wait: bool = False
    strict: bool = False
    exceptions: int = 0


@dataclass(frozen=True)
class Enqueue:
    valid: bool = False
    uop: Uop = Uop()
    vaddr: int = 0
    mask: int = 0
    nc: bool = False
    special_eligible: bool = False
    special_request: bool = False
    vector: bool = False
    aligned_type: int = 0
    replay_feedback: bool = False
    handled: bool = False
    slot: int = 0
    mshr: int = 0
    data_sq: SqPtr = SqPtr()
    address_sq: SqPtr = SqPtr()
    last_beat: bool = False
    need_replay: bool = False
    causes: int = 0
    tlb_id: int = 0
    tlb_full: bool = False
    unaligned_head: bool = False


@dataclass(frozen=True)
class StoreWakeup:
    valid: bool = False
    sq: SqPtr = SqPtr()


@dataclass(frozen=True)
class Refill:
    valid: bool = False
    mshr: int = 0


@dataclass(frozen=True)
class L2Hint:
    valid: bool = False
    mshr: int = 0
    keyword: bool = False


@dataclass(frozen=True)
class TlbHint:
    valid: bool = False
    identity: int = 0
    replay_all: bool = False


@dataclass(frozen=True)
class LqWakeup:
    valid: bool = False
    lq: QueuePtr = QueuePtr()


@dataclass(frozen=True)
class Inputs:
    enqueues: tuple[Enqueue, ...] = (Enqueue(),) * 3
    ready: tuple[bool, ...] = (False,) * 3
    address_wakeups: tuple[StoreWakeup, ...] = (StoreWakeup(),) * 2
    data_wakeups: tuple[StoreWakeup, ...] = (StoreWakeup(),) * 2
    data_writes: tuple[StoreWakeup, ...] = (StoreWakeup(),) * 2
    refills: tuple[Refill, ...] = (Refill(),) * 2
    l2_hints: tuple[L2Hint, ...] = (L2Hint(),) * 2
    slow_tlb: TlbHint = TlbHint()
    fast_tlb: TlbHint = TlbHint()
    mmio: LqWakeup = LqWakeup()
    nc: LqWakeup = LqWakeup()
    address_ready: SqPtr = SqPtr()
    address_bits: int = 0
    data_ready: SqPtr = SqPtr()
    data_bits: int = 0
    dequeue: SqPtr = SqPtr()
    upper: SqPtr = SqPtr()
    sq_empty: bool = False
    writeback: QueuePtr = QueuePtr()
    rar_full: bool = False
    raw_full: bool = False
    head: RobPtr = RobPtr()
    redirect: Redirect = Redirect()
    reset: bool = False
