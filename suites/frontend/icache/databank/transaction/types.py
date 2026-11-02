"""Typed transactions for the ICacheDataBank DUT."""

from __future__ import annotations

from dataclasses import dataclass

from suites.frontend.icache.transactions.sram import SramControls


def unsigned(value: int, bits: int, name: str) -> None:
    if type(value) is not int or not 0 <= value < (1 << bits):
        raise ValueError(f"ICacheDataBank {name} requires an unsigned {bits}-bit integer")


@dataclass(frozen=True, slots=True)
class BankWrite:
    """One way-masked write into the data bank."""

    set_index: int
    waymask: int
    data: int
    code: int = 0

    def __post_init__(self) -> None:
        for name, bits in (("set_index", 8), ("waymask", 4), ("data", 64), ("code", 1)):
            unsigned(getattr(self, name), bits, name)


@dataclass(frozen=True, slots=True)
class BankRead:
    """A request for every way of one set."""

    set_index: int

    def __post_init__(self) -> None:
        unsigned(self.set_index, 8, "set_index")


@dataclass(frozen=True, slots=True)
class BankReadData:
    """Every way's stored word and code, as the bank presents them."""

    data: tuple[int, ...]
    code: tuple[int, ...]

    def __post_init__(self) -> None:
        for name, bits in (("data", 64), ("code", 1)):
            values = getattr(self, name)
            if type(values) not in (tuple, list) or len(values) != 4:
                raise ValueError(f"ICacheDataBank {name} must describe all four physical ways")
            for value in values:
                unsigned(value, bits, name)
            object.__setattr__(self, name, tuple(values))


@dataclass(frozen=True, slots=True)
class BankPortRead:
    """The real four-address, way-enabled bank read (including a zero mask)."""
    set_indices: tuple[int, ...]
    waymask: int = 15

    def __post_init__(self) -> None:
        if type(self.set_indices) not in (tuple, list) or len(self.set_indices) != 4:
            raise ValueError('ICacheDataBank read requires four set indices')
        for value in self.set_indices:
            unsigned(value, 8, 'read set index')
        unsigned(self.waymask, 4, 'read waymask')
        object.__setattr__(self, 'set_indices', tuple(self.set_indices))


@dataclass(frozen=True, slots=True)
class BankBist:
    """One valid MBIST input edge, not an acknowledge or a read response.

    All physical encodings remain available. In this single-port SRAM the
    shared address is addr_rd, truncated by the 256-row macro; addr is retained
    and checked on the wire but is the dual-port write address. A one-way macro
    has no byte-write mask, so be does not inhibit its whole-word write.
    """
    array: int = 0
    all_arrays: int = 0
    readen: int = 1
    writeen: int = 0
    be: int = 0
    addr: int = 0
    addr_rd: int = 0
    indata: int = 0

    def __post_init__(self) -> None:
        for name, width in (('array', 3), ('all_arrays', 1), ('readen', 1),
                ('writeen', 1), ('be', 1), ('addr', 9), ('addr_rd', 9), ('indata', 66)):
            unsigned(getattr(self, name), width, f'MBIST {name}')


@dataclass(frozen=True, slots=True)
class BankCycle:
    """Explicit single-edge offers. Arbitration can leave an offer unaccepted.

    Equal valid cycles are distinct offers, never identities inferred from
    payload equality. Convenience read/write methods wait for readiness first;
    this entry point also represents simultaneous and initialization offers.
    """
    read: BankPortRead | None = None
    write: BankWrite | None = None
    bist: BankBist | None = None
    controls: SramControls | None = None

    def __post_init__(self) -> None:
        for name, kind in (('read', BankPortRead), ('write', BankWrite), ('bist', BankBist)):
            if getattr(self, name) is not None and type(getattr(self, name)) is not kind:
                raise ValueError(f'ICacheDataBank {name} requires {kind.__name__}')
        if self.controls is not None and type(self.controls) is not SramControls:
            raise ValueError('ICacheDataBank controls require SramControls')


@dataclass(frozen=True, slots=True)
class StorageOrigin:
    """Expected storage ancestry from declared input history, not a wire tag."""
    uid: int
    epoch: int
    kind: str
    tick: int
    set_index: int
    way: int

    def __post_init__(self):
        for name in ('uid', 'epoch', 'tick'):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError('ICacheDataBank storage identity requires nonnegative integers')
        unsigned(self.set_index, 8, 'storage index')
        unsigned(self.way, 2, 'storage way')
        if type(self.kind) is not str or self.kind not in ('reset', 'write', 'bist', 'uninitialized'):
            raise ValueError('ICacheDataBank storage origin requires its real input kind')


@dataclass(frozen=True, slots=True)
class BankReadResult:
    uid: int
    epoch: int
    accepted_tick: int
    response_tick: int
    values: BankReadData
    sources: tuple[StorageOrigin, ...]
    known_mask: int = 15

    def __post_init__(self):
        for name in ('uid', 'epoch', 'accepted_tick', 'response_tick'):
            if type(getattr(self, name)) is not int or getattr(self, name) < 0:
                raise ValueError('ICacheDataBank result identity requires nonnegative integers')
        unsigned(self.known_mask, 4, 'known storage mask')
        if type(self.values) is not BankReadData:
            raise ValueError('ICacheDataBank result requires a complete immutable sample')
        if type(self.sources) not in (tuple, list) or len(self.sources) != 4 or any(
                type(source) is not StorageOrigin or source.way != way
                for way, source in enumerate(self.sources)):
            raise ValueError('ICacheDataBank result requires four exact storage ancestors')
        object.__setattr__(self, 'sources', tuple(self.sources))
        if self.accepted_tick != self.response_tick:
            raise ValueError('ICacheDataBank functional result must use its actual latency-one consumption edge')


@dataclass(frozen=True, slots=True)
class BankObservation:
    tick: int
    read_ready: int
    write_ready: int
    entries: BankReadData
    bist_ack: int
    bist_outdata: int
    launched: tuple[int, ...] = ()
    accepted: tuple[int, ...] = ()
    responses: tuple[BankReadResult, ...] = ()

    def __post_init__(self):
        if type(self.tick) is not int or self.tick < 0 or type(self.entries) is not BankReadData:
            raise ValueError('ICacheDataBank observation requires its exact tick and immutable sample')
        for name in ('read_ready', 'write_ready', 'bist_ack'):
            unsigned(getattr(self, name), 1, name)
        unsigned(self.bist_outdata, 66, 'MBIST result')
        for name in ('launched', 'accepted', 'responses'):
            value = getattr(self, name)
            if type(value) not in (tuple, list) or any(
                    type(item) is not BankReadResult if name == 'responses'
                    else type(item) is not int or item < 0 for item in value):
                raise ValueError('ICacheDataBank observation contains a mutable or invalid identity')
            object.__setattr__(self, name, tuple(value))
