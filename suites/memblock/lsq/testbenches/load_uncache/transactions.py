"""Immutable public transactions for the LoadQueueUncache parent DUT.

Request types stay in ``uncache_entry.transactions``; this module carries the
public-response vocabulary and the owner ledger record.
"""
from __future__ import annotations

from dataclasses import dataclass

from suites.memblock.lsq.testbenches.shared.transactions import RobIdentity
from suites.memblock.lsq.testbenches.raw.transactions import FtqPtr
from suites.memblock.lsq.testbenches.uncache_entry.transactions import IdResponse, QueuePtr, Redirect, Request, RobPtr


@dataclass(frozen=True)
class LoadRequest:
    entry: Request
    ftq: FtqPtr = FtqPtr()
    offset: int = 0
    rvc: bool = False
    checkpoint: int = 0
    need_replay: bool = False
    uncache_cause: bool = False


@dataclass(frozen=True)
class BypassQuery:
    lq: QueuePtr
    nc: bool
    mmio: bool


@dataclass(frozen=True)
class BusReturn:
    sid: int
    data: int
    error: bool
    nderr: bool


@dataclass(frozen=True)
class SampledInputs:
    requests: tuple[LoadRequest | None, ...]
    pending: RobPtr
    redirect: Redirect
    bypass: tuple[BypassQuery | None, ...]
    bus_ready: bool
    ack: IdResponse
    returned: BusReturn | None
    reset: bool


@dataclass(frozen=True)
class BypassResponse:
    lane: int
    s1_valid: bool = False
    s1_paddr: int = 0
    s2_valid: bool = False
    s2_data: int = 0
    s2_derr: bool = False
    s2_nderr: bool = False


@dataclass(frozen=True)
class Wakeup:
    flag: bool = False
    value: int = 0


@dataclass(frozen=True)
class Rollback:
    valid: bool = False
    rob: RobIdentity | None = None
    level: bool = False
    checkpoint_id: int = 0


@dataclass(frozen=True)
class ExceptionFault:
    valid: bool = False
    rob: RobIdentity | None = None
    vaddr: int = 0
    gpaddr: int = 0
    hyper: bool = False
    nonleaf: bool = False
    exceptions: int = 0


@dataclass(frozen=True)
class UncacheRequestView:
    valid: bool = False
    addr: int = 0
    vaddr: int = 0
    mask: int = 0
    mid: int = 0
    nc: bool = False
    memory_backed: bool = False
    rob: RobIdentity | None = None


@dataclass(frozen=True)
class Observation:
    request: UncacheRequestView | None = None
    mmio_busy: bool = False
    nc_wakeup: Wakeup | None = None
    mmio_wakeup: Wakeup | None = None
    rollback: Rollback = Rollback()
    exception: ExceptionFault = ExceptionFault()
    bypass: tuple[BypassResponse, ...] = ()
