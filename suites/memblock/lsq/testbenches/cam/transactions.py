from dataclasses import dataclass


@dataclass(frozen=True)
class Write:
    address: int = 0
    value: int = 0
    enabled: bool = False


@dataclass(frozen=True)
class Query:
    value: int = 0
    line: bool = False


@dataclass(frozen=True)
class Request:
    writes: tuple[Write, ...]
    queries: tuple[Query, ...]


@dataclass(frozen=True)
class Observation:
    writes: tuple[Write, ...]
    queries: tuple[Query, ...]
    masks: tuple[int, ...]


@dataclass(frozen=True)
class Commit:
    lane: int
    address: int
    old: int | None
    value: int
    version: int
