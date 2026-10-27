from dataclasses import dataclass


def bitmap(ids):
    return sum(1 << i for i in ids)


@dataclass(frozen=True)
class Request:
    enqueues: tuple[int | None, ...] = (None, None, None)
    removes: tuple[int, ...] = ()
    ready: tuple[int, ...] = ()
    reset: bool = False


@dataclass(frozen=True)
class Observation:
    enqueue_masks: tuple[int, ...]
    remove_mask: int
    ready_mask: int
    reset: bool
    output: int


@dataclass(frozen=True)
class Change:
    before: tuple[int, ...]
    inserted: tuple[int, ...]
    removed: tuple[int, ...]
    conflicts: tuple[int, ...]
    reused: tuple[int, ...]
    reset_kind: str | None = None
