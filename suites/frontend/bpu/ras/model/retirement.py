"""Bounded public-port retirement-gap model, separate from ordered call groups.

The fault stimulus omits retirement notifications, not speculative operations.
Only distinct calls/zero counters and at most thirty-two live queue entries are
modeled here. No sampled DUT value predicts a transition. This is not an FTQ
legality model or a replacement for the ordinary repeated-call reference.
"""
from dataclasses import dataclass, replace
from suites.frontend.bpu.models.configuration import RAS_GROUPS, RAS_SPEC_ENTRIES, RAS_POINTER_MODULUS, ALIGN_BYTES, POSITIONS

from suites.frontend.bpu.ras.model.model import Cell


def unsigned(value, bound, name):
    if type(value) is not int or not 0 <= value < bound:
        raise ValueError(f'{name} must be an unsigned integer below {bound}')
    return value


def pointer(value):
    unsigned(value, RAS_POINTER_MODULUS, 'queue pointer')
    return dict(flag=value // RAS_SPEC_ENTRIES, value=value % RAS_SPEC_ENTRIES)


@dataclass(frozen=True, slots=True)
class Retirement:
    head: int = 0
    cells: tuple[Cell, ...] = (Cell(),) * RAS_GROUPS
    bos: int = 0

    def __post_init__(self):
        unsigned(self.head, RAS_GROUPS, 'committed head')
        unsigned(self.bos, RAS_POINTER_MODULUS, 'BOS')
        if len(self.cells) != RAS_GROUPS:
            raise ValueError('sixteen committed cells are required')
        for cell in self.cells:
            if not isinstance(cell, Cell):
                raise ValueError('expected a retained Cell')
            unsigned(cell.address, 1 << 50, 'return address')
            unsigned(cell.counter, 8, 'repeat counter')

    def native(self):
        return dict(head=self.head, cells=[dict(address=c.address, counter=c.counter) for c in self.cells],
            bos=pointer(self.bos))

    def accept(self, action, *, ssp, tosw, address=None):
        if type(action) is not int or action not in (1, 2):
            raise ValueError('only call/return retirement is in scope; no neutral commits')
        unsigned(ssp, RAS_GROUPS, 'metadata SSP')
        unsigned(tosw, RAS_POINTER_MODULUS, 'metadata TOSW')
        distance = (tosw - self.bos) % RAS_POINTER_MODULUS
        if distance > RAS_SPEC_ENTRIES:
            raise ValueError('retirement metadata must be within the bounded forward window')
        cells, current = list(self.cells), self.cells[self.head]
        if action == 2:
            unsigned(address, 1 << 50, 'call return address')
            if address == current.address and current.counter < 7:
                head = ssp
                cells[head] = Cell(cells[head].address, current.counter + 1)
            else:
                head = (ssp + 1) % RAS_GROUPS
                cells[head] = Cell(address, 0)
            bos = tosw  # Push priority, even when distance exceeds two.
        else:
            if address is not None:
                raise ValueError('returns cannot supply an address')
            head = ssp if current.counter else (ssp - 1) % RAS_GROUPS
            if current.counter:
                cells[head] = Cell(cells[head].address, current.counter - 1)
            bos = (tosw - 1) % RAS_POINTER_MODULUS if distance > 2 else self.bos
        return Retirement(head, tuple(cells), bos)


@dataclass(frozen=True, slots=True)
class QueueCell:
    generation: int = -1
    address: int = 0
    previous: int = 0


@dataclass(frozen=True, slots=True)
class DistinctSpeculation:
    ssp: int = 0
    read: int = RAS_POINTER_MODULUS - 1
    write: int = 0
    cells: tuple[QueueCell, ...] = (QueueCell(),) * RAS_SPEC_ENTRIES

    def __post_init__(self):
        unsigned(self.ssp, RAS_GROUPS, 'speculative SSP')
        unsigned(self.read, RAS_POINTER_MODULUS, 'read pointer')
        unsigned(self.write, RAS_POINTER_MODULUS, 'write pointer')
        if len(self.cells) != RAS_SPEC_ENTRIES or any(not isinstance(cell, QueueCell) for cell in self.cells):
            raise ValueError('thirty-two speculative cells are required')
        for cell in self.cells:
            if type(cell.generation) is not int or not -1 <= cell.generation < RAS_POINTER_MODULUS:
                raise ValueError('invalid queue generation')
            unsigned(cell.address, 1 << 50, 'speculative address')
            unsigned(cell.previous, RAS_POINTER_MODULUS, 'previous pointer')

    def live(self, candidate, retired):
        distance = (self.write - retired.bos) % RAS_POINTER_MODULUS
        if distance > RAS_SPEC_ENTRIES:
            raise ValueError('speculation exceeds the thirty-two-entry bounded window')
        live = (candidate - retired.bos) % RAS_POINTER_MODULUS < distance
        if live and self.cells[candidate % RAS_SPEC_ENTRIES].generation != candidate:
            raise ValueError('a live pointer must name a genuine prior allocation')
        return live

    def top(self, retired):
        return (self.cells[self.read % RAS_SPEC_ENTRIES].address if self.live(self.read, retired)
            else retired.cells[self.ssp].address)

    def metadata(self):
        return dict(ssp=self.ssp, tosw=pointer(self.write))

    def public(self, retired, *, top_retired=None):
        top = self.top(retired if top_retired is None else top_retired)
        return dict(top=top, commit_meta=self.metadata(), redirect_meta=dict(ssp=self.ssp, sctr=0,
            tosr=pointer(self.read), tosw=pointer(self.write), nos=pointer(self.cells[self.read % RAS_SPEC_ENTRIES].previous),
            topRetAddr_addr=top))

    def act(self, action, retired, *, address=None):
        if type(action) is not int or action not in (1, 2):
            raise ValueError('only distinct speculative calls/returns are in scope')
        if any(cell.counter for cell in retired.cells):
            raise ValueError('this speculation model excludes repeated counters')
        self.live(self.read, retired)
        if action == 2:
            unsigned(address, 1 << 50, 'call return address')
            if address == self.top(retired) or self.ssp == RAS_GROUPS - 1:
                raise ValueError('repeats and SSP capacity rollover are outside this scenario')
            if (self.write - retired.bos) % RAS_POINTER_MODULUS >= RAS_SPEC_ENTRIES:
                raise ValueError('a push cannot exceed the bounded queue capacity')
            cells = list(self.cells)
            cells[self.write % RAS_SPEC_ENTRIES] = QueueCell(self.write, address, self.read)
            return DistinctSpeculation(self.ssp + 1, self.write, (self.write + 1) % RAS_POINTER_MODULUS, tuple(cells))
        if address is not None or self.ssp == 0:
            raise ValueError('return requires a non-empty stack and no replacement address')
        read = self.cells[self.read % RAS_SPEC_ENTRIES].previous if self.live(self.read, retired) else self.read
        return replace(self, ssp=self.ssp - 1, read=read)
