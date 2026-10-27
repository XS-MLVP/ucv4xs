"""Bounded call groups, with physical storage retained after logical pop.

No sampled metadata or native state is used to predict a transition. Queue
recovery, empty returns, arbitrary stale SSP and unbounded capacity are outside
this model. Calls/returns retire in the same order as public speculation.
"""
from dataclasses import dataclass
from bpuverify.common.model.configuration import RAS_GROUPS, RAS_SPEC_ENTRIES, RAS_POINTER_MODULUS, ALIGN_BYTES, POSITIONS


@dataclass(frozen=True, slots=True)
class Cell:
    address: int = 0
    counter: int = 0


@dataclass(frozen=True, slots=True)
class Group:
    address: int
    counter: int
    slot: int


@dataclass(frozen=True, slots=True)
class CommittedStack:
    groups: tuple[Group, ...] = (Group(0, 0, 0),)
    cells: tuple[Cell, ...] = (Cell(),) * RAS_GROUPS
    evicted: tuple[Group, ...] = ()

    @property
    def head(self):
        return self.groups[-1].slot

    def projection(self):
        top = self.groups[-1]
        return dict(top=top.address, ssp=top.slot, sctr=top.counter)

    def native(self):
        return dict(head=self.head, cells=[dict(address=cell.address, counter=cell.counter) for cell in self.cells])


def advance(state, action, *, address=None):
    if not isinstance(state, CommittedStack):
        raise ValueError('expected a bounded committed stack')
    if type(action) is not int or action not in (1, 2):
        raise ValueError('only an ordered call or return is modeled')
    if len(state.cells) != RAS_GROUPS or not 1 <= len(state.groups) <= RAS_GROUPS:
        raise ValueError('the DefaultConfig committed capacity is sixteen groups')
    if len({group.slot for group in state.groups}) != len(state.groups):
        raise ValueError('live logical groups cannot alias a physical slot')
    for cell in state.cells:
        if not isinstance(cell, Cell) or type(cell.address) is not int or not 0 <= cell.address < 1 << 50:
            raise ValueError('return addresses are unsigned 50-bit pruned addresses')
        if type(cell.counter) is not int or not 0 <= cell.counter <= 7:
            raise ValueError('repeat counters are unsigned three-bit values')
    for group in state.groups:
        if not isinstance(group, Group) or type(group.slot) is not int or not 0 <= group.slot < RAS_GROUPS:
            raise ValueError('a logical group needs a valid physical slot')
        if Cell(group.address, group.counter) != state.cells[group.slot]:
            raise ValueError('live groups and retained storage disagree')
    groups, cells, evicted = list(state.groups), list(state.cells), state.evicted
    top = groups[-1]
    if action == 2:
        if type(address) is not int or not 0 <= address < 1 << 50:
            raise ValueError('a call needs its independent 50-bit return address')
        if address == top.address and top.counter < 7:
            groups[-1] = Group(address, top.counter + 1, top.slot)
        else:
            following = (top.slot + 1) % RAS_GROUPS
            if len(groups) == RAS_GROUPS:
                if groups[0].slot != following:
                    raise ValueError('a full bounded stack must evict its oldest group')
                evicted += (groups.pop(0),)
            elif any(group.slot == following for group in groups):
                raise ValueError('allocation cannot overwrite a still-live neighbor')
            groups.append(Group(address, 0, following))
        selected = groups[-1]
        cells[selected.slot] = Cell(selected.address, selected.counter)
    else:
        if address is not None:
            raise ValueError('a return must not supply a replacement address')
        if top.counter:
            groups[-1] = Group(top.address, top.counter - 1, top.slot)
            cells[top.slot] = Cell(top.address, top.counter - 1)
        elif len(groups) > 1:
            groups.pop()
        else:
            raise ValueError('bottom/empty return is outside the bounded model')
    return CommittedStack(tuple(groups), tuple(cells), evicted)
