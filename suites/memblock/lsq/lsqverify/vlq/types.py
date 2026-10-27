from dataclasses import dataclass, field


@dataclass(frozen=True)
class QueuePtr:
    flag: bool = False
    value: int = 0

    @classmethod
    def encode(cls, serial, size=120):
        return cls(bool(serial // size % 2), serial % size)


@dataclass(frozen=True)
class RobPtr:
    flag: bool = False
    value: int = 0
    former: bool = True

    @classmethod
    def encode(cls, entry, *, former=True, size=160):
        return cls(bool(entry // size % 2), entry % size, former)


@dataclass(frozen=True)
class Dispatch:
    valid: bool = False
    rob: RobPtr = RobPtr()
    start: QueuePtr = QueuePtr()
    flows: int = 0


@dataclass(frozen=True)
class Writeback:
    valid: bool = False
    index: int = 0
    update_address: bool = False
    replay: bool = False


@dataclass(frozen=True)
class Redirect:
    valid: bool = False
    rob: RobPtr = RobPtr()
    flush_self: bool = False


@dataclass(frozen=True)
class Inputs:
    dispatch: tuple[Dispatch, ...]
    writebacks: tuple[Writeback, ...]
    redirect: Redirect = Redirect()
    reset: bool = False


@dataclass(frozen=True)
class Outputs:
    head: QueuePtr = QueuePtr()
    empty: bool = True
    dequeue_valid: bool = False
    dequeue_count: int = 0
    recovery_valid: bool = False
    recovery_ptr: QueuePtr = QueuePtr()
    recovery_stall: bool = False


@dataclass(frozen=True)
class Observation:
    inputs: Inputs
    outputs: Outputs


@dataclass
class Item:
    uid: int
    position: int
    rob_order: int
    rob: RobPtr
    completed: bool = False


@dataclass(frozen=True)
class Recovery:
    sequence: int
    edge: int
    cancel_count: int
    canceled_uids: tuple[int, ...]
    survivors: tuple[int, ...]
    canceled_indices: tuple[int, ...]
    categories: tuple[str, ...]


@dataclass(frozen=True)
class Change:
    old_head: int
    old_tail: int
    allocated: tuple[Item, ...] = ()
    completed: tuple[int, ...] = ()
    suppressed: tuple[tuple[int, str], ...] = ()
    canceled: tuple[int, ...] = ()
    prepared: tuple[Item, ...] = ()
    reported: tuple[Item, ...] = ()
    started_recovery: Recovery | None = None
    finished_recovery: Recovery | None = None
    clamped_recovery: bool = False
    head_blocked_by: int | None = None
    younger_completed: tuple[int, ...] = ()
    reset_kind: str | None = None
