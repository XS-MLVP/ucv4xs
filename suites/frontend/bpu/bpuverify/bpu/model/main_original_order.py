"""Resolved semantic versions have arrival order, not prediction-age priority."""
from dataclasses import dataclass
from bpuverify.bpu.model.main_service import PC,STREAM_PC,entry_payload
from bpuverify.mbtb.model.semantic import Entry,Target,coordinate,tag
from bpuverify.mbtb.model.replacement import MbtbTwoWayLru

EARLIER,LATER=1,5
INITIAL_TARGET=PC+0x600
TARGETS=(PC+0x800,PC+0xA00)
LATER_TARGET=PC+0x1800
ORDERS=('old-then-young','young-then-old')
PHASES=('serviced-between','retained-under-reads')
COUNTERS=(0,1)
RULES=('real-distinct-originals','source-qualified-inputs','declared-arrival-order',
       'declared-version-visibility','complete-entry-services','independent-direction-services',
       'fresh-unexecuted-sibling','fresh-final-target','immutable-originals')


@dataclass(frozen=True,slots=True)
class Program:
    order:str
    phase:str
    sibling_counter:int

    def __post_init__(self):
        if type(self.order) is not str or self.order not in ORDERS:raise ValueError('declared resolution order required')
        if type(self.phase) is not str or self.phase not in PHASES:raise ValueError('declared service boundary required')
        if type(self.sibling_counter) is not int or self.sibling_counter not in COUNTERS:raise ValueError('weak or strong not-taken sibling required')

    @property
    def label(self):return self.phase+'.'+self.order+'.nt'+str(self.sibling_counter)

    @property
    def order_indices(self):return (0,1) if self.order=='old-then-young' else (1,0)

    @property
    def retained(self):return self.phase=='retained-under-reads'

    @property
    def owner(self):
        lru=MbtbTwoWayLru();lru.allocate() # The conditional sibling is learned first.
        return lru.allocate()           # The earlier indirect instruction is next.

    def effect(self,index):
        if type(index) is not int or index not in (0,1):raise ValueError('one of the two original occurrences required')
        return entry_payload(coordinate(PC)[2],Entry(tag(PC),EARLIER,3,0,Target.encode(PC,TARGETS[index])))

    @property
    def services(self):
        indices=self.order_indices[-1:] if self.retained else self.order_indices
        return tuple(self.effect(index) for index in indices)

    @property
    def final_target(self):return TARGETS[self.order_indices[-1]]

    @property
    def direction(self):return dict(row=coordinate(PC)[2],mask=1<<self.owner,values={str(self.owner):2})

    def state(self):
        return dict(order=self.order,phase=self.phase,sibling_counter=self.sibling_counter,
            original_targets=TARGETS,final_target=self.final_target,capacity_assumption=16,
            full_FTQ_reachability_proved=False,physical_coordinate_enumeration=False)
