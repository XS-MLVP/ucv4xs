"""Reference model for MissTrack (16 entries, install/alloc/train/retire/invalidate/clear).

The address functions are written from `MissTrack.scala` for the generated
configuration (modeId=1): 8-bit index = {XOR of vaddr[47:12] 2-bit pairs,
vaddr[11:6]}; 5-bit hash = XORFold(vaddr[49:14]).
"""
from __future__ import annotations

from dataclasses import dataclass, replace

ENTRIES = 16
WAYS = 4
VADDR_BITS = 50
PADDR_BITS = 48
BLOCK_OFF = 6
IDX_BITS = 8
HASH_BITS = 5
UNTAG_BITS = 14
PG_IDX_BITS = 12
MAX_AGE = 7


def index(va: int) -> int:
    hi = 0
    for bit in range(12, 48, 2):
        hi ^= ((va >> bit) & 0x3)
    low = (va >> 6) & 0x3F
    return ((hi & 0x3) << 6) | low


def hash_vaddr(va: int) -> int:
    value = (va >> UNTAG_BITS) & ((1 << (VADDR_BITS - UNTAG_BITS)) - 1)
    result = 0
    for chunk in range((VADDR_BITS - UNTAG_BITS + HASH_BITS - 1) // HASH_BITS):
        result ^= (value >> (5 * chunk)) & 0x1F
    return result


def block(pa: int) -> int:
    return (pa >> BLOCK_OFF) & ((1 << (PADDR_BITS - BLOCK_OFF)) - 1)


@dataclass(frozen=True)
class Entry:
    valid: bool = False
    idx: int = 0
    src_hash: int = 0
    block_paddr: int = 0
    is_pending: bool = False
    way: int = 0
    mshr_id: int = 0
    age: int = 0


@dataclass(frozen=True)
class Owner:
    valid: bool = False
    vaddr: int = 0
    paddr: int = 0


@dataclass(frozen=True)
class Alloc:
    valid: bool = False
    vaddr: int = 0
    paddr: int = 0
    mshr_id: int = 0


@dataclass(frozen=True)
class Install:
    valid: bool = False
    vaddr: int = 0
    paddr: int = 0
    way: int = 0


@dataclass(frozen=True)
class Invalidate:
    valid: bool = False
    idx: int = 0
    way: int = 0


@dataclass(frozen=True)
class Load:
    s0_valid: bool = False
    s0_vaddr: int = 0
    s1_valid: bool = False
    s1_paddr: int = 0
    s2_valid: bool = False
    s2_vaddr: int = 0
    s2_paddr: int = 0
    s2_way: int = 0
    s2_hit: bool = False


@dataclass(frozen=True)
class Spec:
    valid: int = 0
    candidate: int = 0
    resident: int = 0
    pending: int = 0
    mshr_id: int = 0


@dataclass(frozen=True)
class QueryResult:
    unique: bool
    multi: bool
    entry: Entry | None
    idx: int
    src_hash: int


class MissTrackModel:
    def __init__(self) -> None:
        self.entries = [Entry() for _ in range(ENTRIES)]
        self.queries: list[QueryResult | None] = [None, None, None]
        self.retained: list[QueryResult | None] = [None, None, None]
        self.prev_clear = False
        self.prev_invalidate = Invalidate()
        self.last_grant = 0
        self.inserts = 0

    # ---------------------------------------------------------------- lookup
    def _key_collisions(self, entries: list[Entry]) -> list[bool]:
        collisions = []
        for i, entry in enumerate(entries):
            collisions.append(any(
                j != i and other.valid and other.idx == entry.idx
                and other.src_hash == entry.src_hash
                for j, other in enumerate(entries)
            ))
        return collisions

    def make_query(self, vaddr: int, clear_at_s0: bool = False) -> QueryResult:
        idx = index(vaddr)
        src_hash = hash_vaddr(vaddr)
        collisions = self._key_collisions(self.entries)
        matches = [i for i, entry in enumerate(self.entries)
                   if entry.valid and entry.idx == idx and entry.src_hash == src_hash]
        multi = any(collisions[i] for i in matches)
        unique = bool(matches) and not multi and not clear_at_s0
        entry = self.entries[matches[0]] if matches else None
        return QueryResult(unique=unique, multi=multi, entry=entry,
                           idx=idx, src_hash=src_hash)

    def result(self, lane: int) -> QueryResult | None:
        return self.queries[lane] if self.queries[lane] is not None else self.retained[lane]

    # ---------------------------------------------------------------- spec
    def spec(self, lane: int, load: Load, clear: bool) -> Spec:
        result = self.result(lane)
        multi = bool(result.multi) if result is not None else False
        spec_valid = int(load.s1_valid and not clear and not multi)
        if not spec_valid:
            return Spec()
        if result is None or not result.unique:
            return Spec(valid=1, candidate=1)
        entry = result.entry
        block_pa = block(load.s1_paddr)
        resident = int(bool(not entry.is_pending and entry.block_paddr == block_pa))
        pending = int(bool(entry.is_pending and entry.block_paddr == block_pa))
        candidate = int(not resident and not pending)
        return Spec(valid=1, candidate=candidate, resident=resident,
                    pending=pending, mshr_id=entry.mshr_id)

    # ---------------------------------------------------------------- edge
    def cycle(self, loads: list[Load], allocs: list[Alloc], owners: list[Owner],
              install: Install, invalidate: Invalidate, clear: bool) -> list[Spec]:
        specs = [self.spec(lane, loads[lane], clear) for lane in range(3)]
        entries = list(self.entries)

        def owner_matches(entry: Entry) -> bool:
            if entry.mshr_id >= len(owners):
                return False
            owner = owners[entry.mshr_id]
            return (owner.valid and block(owner.paddr) == entry.block_paddr
                    and index(owner.vaddr) == entry.idx)

        def overlaps(idx: int, way: int, inv: Invalidate) -> bool:
            return inv.valid and inv.idx == idx and bool(inv.way & way)

        maintained = list(entries)
        for i, entry in enumerate(entries):
            if not entry.valid:
                continue
            retired = entry.is_pending and not owner_matches(entry)
            invalidated = (not entry.is_pending
                           and overlaps(entry.idx, entry.way, invalidate))
            updated = replace(entry, age=min(entry.age + 1, MAX_AGE))
            if retired or invalidated:
                updated = replace(updated, valid=False)
            maintained[i] = updated

        events: list[Entry] = []

        def event_entry(va: int, pa: int, way: int, pending: bool, mshr: int) -> Entry:
            return Entry(valid=True, idx=index(va), src_hash=hash_vaddr(va),
                         block_paddr=block(pa), is_pending=pending, way=way,
                         mshr_id=mshr, age=0)

        events.append(event_entry(install.vaddr, install.paddr, install.way, False, 0)
                      if install.valid and install.way.bit_count() == 1 else Entry())
        for alloc in allocs:
            events.append(event_entry(alloc.vaddr, alloc.paddr, 0, True, alloc.mshr_id)
                          if alloc.valid else Entry())
        for load in loads:
            train = (load.s2_valid and load.s2_hit and load.s2_way.bit_count() == 1
                     and not self.prev_clear
                     and not overlaps(index(load.s2_vaddr), load.s2_way, invalidate)
                     and not overlaps(index(load.s2_vaddr), load.s2_way,
                                      self.prev_invalidate))
            events.append(event_entry(load.s2_vaddr, load.s2_paddr, load.s2_way, False, 0)
                          if train else Entry())

        canonical = []
        for i, event in enumerate(events):
            shadowed = any(events[j].valid and events[j].idx == event.idx
                           and events[j].block_paddr == event.block_paddr
                           for j in range(i))
            canonical.append(event.valid and not shadowed)

        event_matches = [
            [entries[i].valid and event.idx == entries[i].idx
             and event.block_paddr == entries[i].block_paddr for event in events]
            for i in range(ENTRIES)
        ]
        for i in range(ENTRIES):
            hits = [j for j in range(len(events)) if event_matches[i][j]]
            if hits:
                winner = events[hits[0]]
                maintained[i] = replace(winner, idx=entries[i].idx,
                                        block_paddr=entries[i].block_paddr)

        candidates = [j for j in range(len(events))
                      if canonical[j] and not any(event_matches[i][j]
                                                  for i in range(ENTRIES))]
        next_entries = list(maintained)
        if candidates and not clear:
            order = [(self.last_grant + 1 + k) % len(events) for k in range(len(events))]
            chosen = next(j for j in order if j in candidates)
            self.last_grant = chosen
            invalid = [i for i in range(ENTRIES) if not maintained[i].valid]
            if invalid:
                victim = invalid[0]
            else:
                victim = 0
                for i in range(1, ENTRIES):
                    if maintained[i].age > maintained[victim].age:
                        victim = i
            next_entries[victim] = events[chosen]
            self.inserts += 1
        if clear:
            next_entries = [replace(entry, valid=False) for entry in next_entries]

        # Capture the S0 query against the pre-edge table.
        new_queries = []
        for load in loads:
            new_queries.append(self.make_query(load.s0_vaddr, clear)
                               if load.s0_valid else None)
        for lane in range(3):
            if self.queries[lane] is not None:
                self.retained[lane] = self.queries[lane]

        self.entries = next_entries
        self.queries = new_queries
        self.prev_clear = clear
        self.prev_invalidate = invalidate
        return specs

    def dump(self) -> list[Entry]:
        return list(self.entries)
