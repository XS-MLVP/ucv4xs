from dataclasses import dataclass


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
class Redirect:
    valid: bool = False
    rob: RobPtr = RobPtr()
    flush_self: bool = False
