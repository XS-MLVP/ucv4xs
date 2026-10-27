"""Bounded public-port retirement-gap model, separate from ordered call groups.

The fault stimulus omits retirement notifications, not speculative operations.
Only distinct calls/zero counters and at most sixteen live queue entries are
modeled here. No sampled DUT value predicts a transition. This is not an FTQ
legality model or a replacement for the ordinary repeated-call reference.
"""
from dataclasses import dataclass, replace

from bpuverify.ras.model.model import Cell


def unsigned(value, bound, name):
    if type(value) is not int or not 0 <= value < bound:
        raise ValueError(f'{name} must be an unsigned integer below {bound}')
    return value


def pointer(value):
    unsigned(value, 32, 'queue pointer')
    return dict(flag=value // 16, value=value % 16)


@dataclass(frozen=True, slots=True)
class Retirement:
    head: int = 0
    cells: tuple[Cell, ...] = (Cell(),) * 8
    bos: int = 0

    def __post_init__(self):
        unsigned(self.head, 8, 'committed head')
        unsigned(self.bos, 32, 'BOS')
        if len(self.cells) != 8:
            raise ValueError('eight committed cells are required')
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
        unsigned(ssp, 8, 'metadata SSP')
        unsigned(tosw, 32, 'metadata TOSW')
        distance = (tosw - self.bos) % 32
        if distance > 16:
            raise ValueError('retirement metadata must be within the bounded forward window')
        cells, current = list(self.cells), self.cells[self.head]
        if action == 2:
            unsigned(address, 1 << 50, 'call return address')
            if address == current.address and current.counter < 7:
                head = ssp
                cells[head] = Cell(cells[head].address, current.counter + 1)
            else:
                head = (ssp + 1) % 8
                cells[head] = Cell(address, 0)
            bos = tosw  # Push priority, even when distance exceeds two.
        else:
            if address is not None:
                raise ValueError('returns cannot supply an address')
            head = ssp if current.counter else (ssp - 1) % 8
            if current.counter:
                cells[head] = Cell(cells[head].address, current.counter - 1)
            bos = (tosw - 1) % 32 if distance > 2 else self.bos
        return Retirement(head, tuple(cells), bos)


@dataclass(frozen=True, slots=True)
class QueueCell:
    generation: int = -1
    address: int = 0
    previous: int = 0


@dataclass(frozen=True, slots=True)
class DistinctSpeculation:
    ssp: int = 0
    read: int = 31
    write: int = 0
    cells: tuple[QueueCell, ...] = (QueueCell(),) * 16

    def __post_init__(self):
        unsigned(self.ssp, 8, 'speculative SSP')
        unsigned(self.read, 32, 'read pointer')
        unsigned(self.write, 32, 'write pointer')
        if len(self.cells) != 16 or any(not isinstance(cell, QueueCell) for cell in self.cells):
            raise ValueError('sixteen speculative cells are required')
        for cell in self.cells:
            if type(cell.generation) is not int or not -1 <= cell.generation < 32:
                raise ValueError('invalid queue generation')
            unsigned(cell.address, 1 << 50, 'speculative address')
            unsigned(cell.previous, 32, 'previous pointer')

    def live(self, candidate, retired):
        distance = (self.write - retired.bos) % 32
        if distance > 16:
            raise ValueError('speculation exceeds the sixteen-entry bounded window')
        live = (candidate - retired.bos) % 32 < distance
        if live and self.cells[candidate % 16].generation != candidate:
            raise ValueError('a live pointer must name a genuine prior allocation')
        return live

    def top(self, retired):
        return (self.cells[self.read % 16].address if self.live(self.read, retired)
            else retired.cells[self.ssp].address)

    def metadata(self):
        return dict(ssp=self.ssp, tosw=pointer(self.write))

    def public(self, retired, *, top_retired=None):
        top = self.top(retired if top_retired is None else top_retired)
        return dict(top=top, commit_meta=self.metadata(), redirect_meta=dict(ssp=self.ssp, sctr=0,
            tosr=pointer(self.read), tosw=pointer(self.write), nos=pointer(self.cells[self.read % 16].previous),
            topRetAddr_addr=top))

    def act(self, action, retired, *, address=None):
        if type(action) is not int or action not in (1, 2):
            raise ValueError('only distinct speculative calls/returns are in scope')
        if any(cell.counter for cell in retired.cells):
            raise ValueError('this speculation model excludes repeated counters')
        self.live(self.read, retired)
        if action == 2:
            unsigned(address, 1 << 50, 'call return address')
            if address == self.top(retired) or self.ssp == 7:
                raise ValueError('repeats and SSP capacity rollover are outside this scenario')
            if (self.write - retired.bos) % 32 >= 16:
                raise ValueError('a push cannot exceed the bounded queue capacity')
            cells = list(self.cells)
            cells[self.write % 16] = QueueCell(self.write, address, self.read)
            return DistinctSpeculation(self.ssp + 1, self.write, (self.write + 1) % 32, tuple(cells))
        if address is not None or self.ssp == 0:
            raise ValueError('return requires a non-empty stack and no replacement address')
        read = self.cells[self.read % 16].previous if self.live(self.read, retired) else self.read
        return replace(self, ssp=self.ssp - 1, read=read)
