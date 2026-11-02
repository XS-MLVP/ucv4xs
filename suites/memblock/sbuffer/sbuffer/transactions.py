"""Immutable public transactions; no generated signals escape into testcases."""
from __future__ import annotations

from dataclasses import dataclass

from .model import Enq


@dataclass(frozen=True)
class Controls:
    timeout: int = 0
    force_write: bool = False
    sq_empty: bool = True
    misses_empty: bool = True
    flush: bool = False
    cmo: bool = False


@dataclass(frozen=True)
class Cycle:
    controls: Controls = Controls()
    reset: bool = False
    enqueues: tuple[tuple[int, Enq], ...] = ()
    accept_request: bool = False
    hit: int | None = None
    replay: int | None = None
    forward_s0: tuple[int, int] | None = None  # load lane, virtual address
    forward_s1: tuple[int, int, bool] | None = None  # lane, physical address, kill


@dataclass(frozen=True)
class Request:
    id: int
    addr: int
    vaddr: int
    mask: int
    data: int


@dataclass(frozen=True)
class Writeback(Request):
    """One caller/model-owned line identity and one accepted-attempt ordinal."""
    uid: int
    attempt: int

    @property
    def retry(self) -> bool:
        return self.attempt > 1


@dataclass(frozen=True)
class Status:
    empty: bool
    full: bool
    request_pending: bool
    flush_complete: bool
    enqueue_ready: tuple[bool, bool]


@dataclass(frozen=True)
class ForwardResult:
    mask: int
    data: tuple[int, ...]
    invalid: bool


@dataclass(frozen=True)
class Observation:
    reset: bool
    enqueues: tuple[tuple[int, Enq, bool], ...]
    request: Request | None
    request_fire: bool
    hit: int | None
    replay: int | None


@dataclass(frozen=True)
class Event:
    kind: str
    uid: int
    attempt: int
    slot: int
    tick: int
