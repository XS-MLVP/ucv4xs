"""Predeclared branch learning program, independent of DUT data and timing.

Addresses represent adjacent architectural windows across a page boundary.
Capacity and LRU belong to this configuration; neither observed ways nor
invalid metadata counters are used to construct the expected residents.
"""
from dataclasses import dataclass, replace
from suites.frontend.bpu.mbtb.model.replacement import MbtbFourWayLru

MODES = ('serial', 'adjacent')
ORDERS = ('forward', 'reverse')
POSITION_RELATIONS = ('same-position', 'new-position')
PC, NEIGHBOR = 0x40000FF0, 0x40001000  # halfword addresses
TAG_STRIDE = 1 << 15
RULES = ('full-distinct-old-residents', 'original-overlapping-cold-sources',
         'actual-feedback-cadence', 'two-new-identities-and-directions',
         'old-residents-retired', 'independent-window-content',
         'target-next-victim', 'independent-next-victim', 'immutable-original-sources')


@dataclass(frozen=True, slots=True)
class Branch:
    owner: str
    pc: int
    position: int
    target: int
    kind: int = 1
    action: int = 0
    counter: int = 2
    way: int = -1

    def values(self):
        return (((self.pc // 16) % 2) * 5 + self.way, self.position, self.target,
                int(self.kind != 1 or self.counter >= 2), self.kind, self.action, self.counter)


class FullCapacityProgram:
    """Logical allocation order and branch-owned direction learning only."""

    def __init__(self, order, *, position_relation='same-position'):
        if order not in ORDERS:
            raise ValueError('unknown semantic input order')
        if position_relation not in POSITION_RELATIONS:
            raise ValueError('unknown semantic position relation')
        self.order, self.position_relation = order, position_relation
        new_positions = (1, 1) if position_relation == 'same-position' else (2, 4)
        self.branches = {r.owner: r for r in (
            Branch('old-a', PC, 1, 0x40008020),
            Branch('old-b', PC + TAG_STRIDE, 5, 0x40008140),
            Branch('old-c', PC + 5 * TAG_STRIDE, 7, 0x40008240),
            Branch('old-d', PC + 6 * TAG_STRIDE, 9, 0x40008340),
            Branch('new-a', PC + 2 * TAG_STRIDE, new_positions[0], 0x40009260),
            Branch('new-b', PC + 3 * TAG_STRIDE, new_positions[1], 0x4000A380),
            Branch('target-probe', PC + 4 * TAG_STRIDE, 3, 0x4000B4A0),
            Branch('neighbor-a', NEIGHBOR, 3, 0x4000C5C0),
            Branch('neighbor-b', NEIGHBOR + TAG_STRIDE, 5, 0x4000D6E0, kind=2, action=1),
            Branch('neighbor-probe', NEIGHBOR + 2 * TAG_STRIDE, 1, 0x4000E800),
            Branch('neighbor-c', NEIGHBOR + 3 * TAG_STRIDE, 7, 0x4000D800),
            Branch('neighbor-d', NEIGHBOR + 4 * TAG_STRIDE, 9, 0x4000DA00),
        )}
        self.sequence = ('new-a', 'new-b') if order == 'forward' else ('new-b', 'new-a')
        residents, displaced = {}, {}
        ages = {name:MbtbFourWayLru() for name in ('target','neighbor')}
        self.stages, self.victims = {}, {}

        def group(owner):
            return 'neighbor' if owner.startswith('neighbor') else 'target'

        def allocate(owner):
            r = self.branches[owner]
            way = ages[group(owner)].allocate()
            for old, resident in tuple(residents.items()):
                if group(old) == group(owner) and resident.way == way:
                    displaced[old] = replace(resident,way=4,counter=2)
                    del residents[old]
            residents[owner] = replace(r, way=way)

        def learn(owner, taken):
            r = residents[owner]
            residents[owner] = replace(r, counter=max(0, min(3, r.counter + (1 if taken else -1))))
            if taken:
                ages[group(owner)].touch(r.way)

        def save(stage):
            self.stages[stage] = (*residents.values(),*displaced.values())
            self.victims[stage] = {name:age.victim for name,age in ages.items()}

        allocate('old-a'); allocate('old-b')
        learn('old-a', False); learn('old-a', False); learn('old-b', True)
        allocate('old-c'); allocate('old-d')
        allocate('neighbor-a'); allocate('neighbor-b')
        allocate('neighbor-c'); allocate('neighbor-d'); learn('neighbor-a', True)
        save('prepared')
        for owner in self.sequence:
            allocate(owner)
        save('pair')
        allocate('neighbor-probe'); save('neighbor-probe')
        # Observe neighbor's opposite victim BEFORE a target allocation can
        # mask a bad cross-index update. Its survivor touch then restores
        # neighbor victim0 while target must still select victim1.
        learn('neighbor-a', True); save('neighbor-touch')
        allocate('target-probe'); save('target-probe')

    def profile(self, stage, owner):
        pc = self.branches[owner].pc
        return tuple(r.values() for r in self.stages[stage] if r.pc == pc)

    def raw_hits(self, stage, owner):
        # Main metadata reports tag hits even when the adjacent window is
        # suppressed at a page boundary. Victim results remain qualified.
        pc = self.branches[owner].pc
        hits = [0] * 10
        for address in (pc, (pc // 16 + 1) * 16):
            for record in self.stages[stage]:
                if record.pc != address:
                    continue
                if record.way == 4 and address // 2048 != pc // 2048:
                    continue
                hits[((address // 16) % 2) * 5 + record.way] = 1
        return tuple(hits)

    def state(self):
        return dict(order=self.order, position_relation=self.position_relation,
                    sequence=self.sequence, stages=self.stages, victims=self.victims)
