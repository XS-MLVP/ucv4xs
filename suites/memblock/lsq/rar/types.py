from dataclasses import dataclass

from suites.memblock.lsq.vlq.types import QueuePtr, Redirect, RobPtr


@dataclass(frozen=True)
class Query:
    valid: bool = False
    rob: RobPtr = RobPtr()
    lq: QueuePtr = QueuePtr()
    paddr: int = 0
    data_valid: bool = False
    nc: bool = False


@dataclass(frozen=True)
class Release:
    valid: bool = False
    paddr: int = 0


@dataclass(frozen=True)
class Inputs:
    queries: tuple[Query, ...]
    revoke_last: tuple[bool, ...]
    revoke_older: tuple[bool, ...]
    head: QueuePtr = QueuePtr()
    redirect: Redirect = Redirect()
    release: Release = Release()
    reset: bool = False


@dataclass(frozen=True)
class Response:
    valid: bool = False
    nuke: bool = False


@dataclass(frozen=True)
class Outputs:
    ready: tuple[bool, ...]
    responses: tuple[Response, ...]
    full: bool
    perf_fire: int
    perf_nuke: int


@dataclass(frozen=True)
class Entry:
    uid: int
    slot: int
    rob_order: int
    lq_position: int
    query: Query
    key: int
    released: bool
    release_source: str
    release_edge: int
    alias_window: bool = False


@dataclass(frozen=True)
class Freed:
    item: Entry
    causes: tuple[str, ...]


@dataclass(frozen=True)
class Change:
    before: tuple[Entry, ...] = ()
    allocated: tuple[Entry, ...] = ()
    freed: tuple[Freed, ...] = ()
    matches: tuple[tuple[int, ...], ...] = ()
    needed: tuple[bool, ...] = ()
    accepted: tuple[int | None, ...] = ()
    query_orders: tuple[int | None, ...] = ()
    query_positions: tuple[int | None, ...] = ()
    newly_released: tuple[int, ...] = ()
    recycled_slots: tuple[int, ...] = ()
    old_available: int = 96
    new_available: int = 96
    head_before: int = 0
    head_after: int = 0
    perf_fire_source: int = 0
    perf_alloc_source: int = 0
    reset_kind: str | None = None
