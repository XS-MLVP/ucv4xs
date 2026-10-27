"""Only retained public wrapper inputs; no externally writable SQ feedback."""
from dataclasses import dataclass

from lsqverify.forward.types import Query, Translation
from lsqverify.load_queue.types import Bus as LoadBus, Bypass, Load
from lsqverify.psq.types import Address as PhysicalAddress, Attributes, SecondPage
from lsqverify.rar.types import Query as RarQuery, Release
from lsqverify.raw.types import FtqPtr, Query as RawQuery, SqPtr
from lsqverify.replay.types import L2Hint, Refill, StoreWakeup, TlbHint
from lsqverify.vlq.types import QueuePtr, Redirect, RobPtr


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
