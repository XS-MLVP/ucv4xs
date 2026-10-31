from dataclasses import dataclass

from suites.memblock.lsq.vlq.types import Redirect, RobPtr


@dataclass(frozen=True)
class SqPtr:
    first: bool = False
    second: bool = False
    value: int = 0

    @classmethod
    def encode(cls, position, physical_entries=64, multiple=2):
        raw = position % (2 * multiple * physical_entries)
        return cls(bool(raw // (multiple * physical_entries)), bool(raw // physical_entries % multiple), raw % physical_entries)


@dataclass(frozen=True)
class FtqPtr:
    flag: bool = False
    value: int = 0


@dataclass(frozen=True)
class Query:
    valid: bool = False
    rob: RobPtr = RobPtr()
    sq: SqPtr = SqPtr()
    paddr: int = 0
    mask: int = 0
    data_valid: bool = False
    is_rvc: bool = False
    ftq: FtqPtr = FtqPtr()
    ftq_offset: int = 0
    checkpoint: int = 0


@dataclass(frozen=True)
class Store:
    valid: bool = False
    rob: RobPtr = RobPtr()
    paddr: int = 0
    mask: int = 0
    wline: bool = False
    tlb_miss: bool = False
    ftq_flag: bool = False
    ftq_value: int = 0
    ftq_offset: int = 0
    is_rvc: bool = False


@dataclass(frozen=True)
class Inputs:
    queries: tuple[Query, ...]
    stores: tuple[Store, ...]
    revoke_last: tuple[bool, ...]
    revoke_older: tuple[bool, ...]
    head: SqPtr = SqPtr()
    redirect: Redirect = Redirect()
    reset: bool = False


@dataclass(frozen=True)
class Rollback:
    valid: bool = False
    rob: RobPtr = RobPtr()
    ftq: FtqPtr = FtqPtr()
    ftq_offset: int = 0
    is_rvc: bool = False
    checkpoint: int = 0
    store_ftq_flag: bool = False
    store_ftq_value: int = 0
    store_ftq_offset: int = 0
    store_is_rvc: bool = False


@dataclass(frozen=True)
class Training:
    valid: bool = False
    ftq_value: int = 0
    ftq_offset: int = 0
    is_rvc: bool = False
    store_ftq_value: int = 0
    store_ftq_offset: int = 0
    store_is_rvc: bool = False


@dataclass(frozen=True)
class Outputs:
    ready: tuple[bool, ...]
    full: bool
    rollbacks: tuple[Rollback, ...]
    training: Training
    perf_fire: int
    perf_rollback: int


@dataclass(frozen=True)
class Entry:
    uid: int
    slot: int
    rob_order: int
    sq_position: int
    query: Query


@dataclass(frozen=True)
class Freed:
    item: Entry
    causes: tuple[str, ...]


@dataclass(frozen=True)
class Selection:
    uid: int
    born: int
    due: int
    lane: int
    store: Store
    store_order: int
    winner: Entry | None
    candidates: tuple[int, ...]
    canceled: bool = False


@dataclass(frozen=True)
class Change:
    before: tuple[Entry, ...] = ()
    allocated: tuple[Entry, ...] = ()
    freed: tuple[Freed, ...] = ()
    needed: tuple[bool, ...] = ()
    accepted: tuple[int | None, ...] = ()
    query_orders: tuple[int | None, ...] = ()
    query_positions: tuple[int | None, ...] = ()
    created: tuple[Selection, ...] = ()
    emitted: tuple[Selection, ...] = ()
    canceled_jobs: tuple[int, ...] = ()
    recycled_slots: tuple[int, ...] = ()
    old_available: int = 56
    new_available: int = 56
    old_offered: int = 3
    new_offered: int = 3
    head_before: int = 0
    head_after: int = 0
    perf_fire_source: int = 0
    perf_alloc_source: int = 0
    reset_kind: str | None = None
