"""Typed transactions for the ICacheMetaInterleavedBank DUT."""

from __future__ import annotations

from dataclasses import dataclass

from suites.frontend.icache.testbenches.shared.transactions.sram import SramControls


def unsigned(value, width, name):
    if type(value) is not int or not 0 <= value < (1 << width):
        raise ValueError(f'ICacheMetaBank {name} requires an unsigned {width}-bit integer')


@dataclass(frozen=True, slots=True)
class MetaBankWrite:
    """One way-masked metadata fill."""

    set_index: int
    waymask: int
    phy_tag: int
    maybe_rvc_map: int = 0
    code: int = 0

    def __post_init__(self):
        for name, width in (('set_index', 7), ('waymask', 4), ('phy_tag', 36),
                            ('maybe_rvc_map', 32), ('code', 1)):
            unsigned(getattr(self, name), width, name)


@dataclass(frozen=True, slots=True)
class MetaBankRead:
    """A request for every way of one set."""

    set_index: int

    def __post_init__(self):
        unsigned(self.set_index, 7, 'read set index')


@dataclass(frozen=True, slots=True)
class MetaBankWay:
    """One way's metadata plus the valid bit that gates its use."""

    valid: int
    phy_tag: int
    maybe_rvc_map: int
    code: int

    def __post_init__(self):
        for name, width in (('valid', 1), ('phy_tag', 36), ('maybe_rvc_map', 32), ('code', 1)):
            unsigned(getattr(self, name), width, name)

    @classmethod
    def from_word(cls, valid, word):
        return cls(valid, word >> 33, (word >> 1) & ((1 << 32) - 1), word & 1)


@dataclass(frozen=True, slots=True)
class MetaBankBist:
    """One valid test-input edge. Two macros, two69-bit ways per macro."""
    array: int = 0
    all_arrays: int = 0
    readen: int = 1
    writeen: int = 0
    be: int = 0
    addr: int = 0
    addr_rd: int = 0
    indata: int = 0

    def __post_init__(self):
        for name, width in (('array', 1), ('all_arrays', 1), ('readen', 1),
                ('writeen', 1), ('be', 2), ('addr', 8), ('addr_rd', 8), ('indata', 138)):
            unsigned(getattr(self, name), width, 'MBIST ' + name)


@dataclass(frozen=True, slots=True)
class MetaBankCycle:
    read: MetaBankRead | None = None
    write: MetaBankWrite | None = None
    flush_all: int = 0
    bist: MetaBankBist | None = None
    controls: SramControls | None = None

    def __post_init__(self):
        unsigned(self.flush_all, 1, 'flushAll')
        for name, kind in (('read', MetaBankRead), ('write', MetaBankWrite), ('bist', MetaBankBist)):
            if getattr(self, name) is not None and type(getattr(self, name)) is not kind:
                raise ValueError(f'ICacheMetaBank {name} requires {kind.__name__}')
        if self.controls is not None and type(self.controls) is not SramControls:
            raise ValueError('ICacheMetaBank controls require SramControls')


@dataclass(frozen=True, slots=True)
class MetaOrigin:
    uid: int
    epoch: int
    kind: str
    tick: int
    set_index: int
    way: int

    def __post_init__(self):
        for name in ('uid', 'epoch', 'tick'):
            if type(getattr(self, name)) is not int or getattr(self, name) < 0:
                raise ValueError('ICacheMetaBank ancestry requires nonnegative exact identity/times')
        unsigned(self.set_index, 7, 'ancestor index')
        unsigned(self.way, 2, 'ancestor way')
        if type(self.kind) is not str or self.kind not in ('reset', 'write', 'bist', 'flush', 'uninitialized'):
            raise ValueError('ICacheMetaBank ancestry requires its real input kind')


def ways(values):
    if type(values) not in (tuple, list) or len(values) != 4 or any(type(value) is not MetaBankWay for value in values):
        raise ValueError('ICacheMetaBank sample requires all four immutable ways')
    return tuple(values)


@dataclass(frozen=True, slots=True)
class MetaReadResult:
    uid: int
    epoch: int
    accepted_tick: int
    response_tick: int
    values: tuple[MetaBankWay, ...]
    storage_sources: tuple[MetaOrigin, ...]
    validity_sources: tuple[MetaOrigin, ...]
    known_mask: int = 15

    def __post_init__(self):
        for name in ('uid', 'epoch', 'accepted_tick', 'response_tick'):
            if type(getattr(self, name)) is not int or getattr(self, name) < 0:
                raise ValueError('ICacheMetaBank result requires exact nonnegative identity/times')
        unsigned(self.known_mask, 4, 'known storage mask')
        if self.accepted_tick != self.response_tick:
            raise ValueError('ICacheMetaBank result must use its actual consumption/response boundary')
        object.__setattr__(self, 'values', ways(self.values))
        for name in ('storage_sources', 'validity_sources'):
            sources = getattr(self, name)
            if type(sources) not in (tuple, list) or len(sources) != 4 or any(
                    type(value) is not MetaOrigin or value.way != index for index, value in enumerate(sources)):
                raise ValueError('ICacheMetaBank result requires four exact memory/valid ancestors')
            object.__setattr__(self, name, tuple(sources))


@dataclass(frozen=True, slots=True)
class MetaObservation:
    tick: int
    read_ready: int
    write_ready: int
    entries: tuple[MetaBankWay, ...]
    bist_ack: int
    bist_outdata: int
    launched: tuple[int, ...] = ()
    accepted: tuple[int, ...] = ()
    responses: tuple[MetaReadResult, ...] = ()

    def __post_init__(self):
        if type(self.tick) is not int or self.tick < 0:
            raise ValueError('ICacheMetaBank observation requires its exact tick')
        for name in ('read_ready', 'write_ready', 'bist_ack'):
            unsigned(getattr(self, name), 1, name)
        unsigned(self.bist_outdata, 138, 'test-port response')
        object.__setattr__(self, 'entries', ways(self.entries))
        for name in ('launched', 'accepted', 'responses'):
            values = getattr(self, name)
            if type(values) not in (tuple, list) or any(
                    type(value) is not MetaReadResult if name == 'responses'
                    else type(value) is not int or value < 0 for value in values):
                raise ValueError('ICacheMetaBank observation contains an invalid identity')
            object.__setattr__(self, name, tuple(values))
