"""Original miss authority is independent of allocator and stale payload position."""
from dataclasses import dataclass
from bpuverify.bpu.model.main_service import PC,STREAM_PC
from bpuverify.mbtb.model.semantic import coordinate,tag

FOREIGN_PC=PC+0x10000
RESIDENT_POSITION,OTHER_POSITION=7,6
RULES=('normally-learned-resident','actual-original-cold-miss','complete-literal-feedback-once',
    'source-lifetime-qualified','entry-allocation-ownership','direction-authority',
    'actual-direction-service','fresh-independent-consumers','immutable-original-metadata')


@dataclass(frozen=True)
class Program:
    allocate:bool
    same_position:bool

    def __post_init__(self):
        if type(self.allocate) is not bool or type(self.same_position) is not bool:
            raise ValueError('declared allocation intent and position relation required')
        if coordinate(PC)!=coordinate(FOREIGN_PC) or tag(PC)==tag(FOREIGN_PC):
            raise ValueError('one logical foreign tag at the same committed row required')
    @property
    def label(self):return ('allocate' if self.allocate else 'no-allocation')+'.'+('same-position' if self.same_position else 'other-position')
    @property
    def position(self):return RESIDENT_POSITION if self.same_position else OTHER_POSITION
    @property
    def taken(self):return int(self.allocate)
    @property
    def direction(self):return dict(row=coordinate(PC)[2],mask=1,values={'0':2}) if self.allocate else None
    def state(self):return dict(allocate=self.allocate,same_position=self.same_position,pc=PC,foreign_pc=FOREIGN_PC,
        resident_position=RESIDENT_POSITION,feedback_position=self.position,resident_counter=2,
        semantic_event='miss payload cannot train a resident; allocation initializes only its new identity',
        original_source_only=True,physical_enumeration=False,full_FTQ_reachability_proved=False)
