"""Public load queries, store byte records and cross-page hints."""
from dataclasses import dataclass

from lsqverify.raw.types import SqPtr


def byte_count(size):
    if not 0 <= size < 8:
        raise ValueError("MemorySize is 3 bits; all Q encodings 4..7 mean 16 bytes")
    return 1 << min(size, 4)


def sq_serial(ptr):
    if not 0 <= ptr.value < 64:
        raise ValueError("physical SQ index is 6 bits")
    return int(ptr.first) * 128 + int(ptr.second) * 64 + ptr.value


@dataclass(frozen=True)
class Store:
    size: int = 0
    vaddr: int = 0
    page: int = 0
    mask: int = 0
    data: int = 0
    cbo: int = 0
    data_ready: bool = False
    address_ready: bool = False
    cross_word: bool = False
    cache_operation: bool = False

    @property
    def paddr(self):
        return self.page * 4096 + self.vaddr % 4096

    @property
    def length(self):
        return byte_count(self.size)


@dataclass(frozen=True)
class Query:
    valid: bool = False
    vaddr: int = 0
    sq: SqPtr = SqPtr()
    size: int = 0
    wait: bool = False
    strict: bool = False
    wait_sq: SqPtr = SqPtr()


@dataclass(frozen=True)
class Translation:
    paddr: int = 0
    kill: bool = False


@dataclass(frozen=True)
class SecondPage:
    valid: bool = False
    paddr: int = 0
    sq: SqPtr = SqPtr()


@dataclass(frozen=True)
class Inputs:
    queries: tuple[Query, ...] = (Query(),) * 3
    translations: tuple[Translation, ...] = (Translation(),) * 3
    stores: tuple[Store, ...] = (Store(),) * 64
    second_pages: tuple[SecondPage, ...] = (SecondPage(),) * 2
    dequeue: SqPtr = SqPtr()
    upper: SqPtr = SqPtr(False, True, 0)
