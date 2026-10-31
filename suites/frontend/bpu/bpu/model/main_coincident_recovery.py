"""Same-boundary acceptance owns learning; recovery owns younger predictions."""
from dataclasses import dataclass
from suites.frontend.bpu.bpu.model.main_accepted_recovery import FATES,RULES as PRIOR_RULES
from suites.frontend.bpu.bpu.model.main_original_order import Program as OriginalProgram,PC,EARLIER,TARGETS
from suites.frontend.bpu.bpu.model.main_service import entry_payload
from suites.frontend.bpu.mbtb.model.semantic import Entry,Target,coordinate,tag

REVISIONS=('dynamic-target','becomes-direct')
COUNTERS=(0,1)
RULES=tuple('input-qualified-at-recovery' if r=='input-qualified-before-recovery' else r for r in PRIOR_RULES)


@dataclass(frozen=True,slots=True)
class Program:
    fate:str
    revision:str
    sibling_counter:int

    def __post_init__(self):
        if self.fate not in FATES or self.revision not in REVISIONS or type(self.sibling_counter) is not int or self.sibling_counter not in COUNTERS:
            raise ValueError('declared source fate, real instruction revision and NT sibling confidence required')
    @property
    def label(self):return self.fate+'.'+self.revision+'.nt'+str(self.sibling_counter)
    @property
    def simultaneous(self):return True
    @property
    def cancelled(self):return self.fate=='source-cancelled'
    @property
    def restore_index(self):return 0 if self.cancelled else 1
    @property
    def moment(self):return 'same-boundary'
    @property
    def kind(self):return 3 if self.revision=='dynamic-target' else 2
    @property
    def target(self):return TARGETS[0]
    @property
    def original(self):return OriginalProgram('old-then-young','retained-under-reads',self.sibling_counter)
    @property
    def owner(self):return self.original.owner
    @property
    def direction(self):return self.original.direction
    @property
    def effect(self):
        return entry_payload(coordinate(PC)[2],Entry(tag(PC),EARLIER,self.kind,0,Target.encode(PC,self.target)))
    @property
    def services(self):return (self.effect,)
    def state(self):
        return dict(fate=self.fate,revision=self.revision,sibling_counter=self.sibling_counter,
            target=self.target,kind=self.kind,restore_index=self.restore_index,
            expected_source_cancelled=self.cancelled,simultaneous_input_and_external_recovery=True,
            capacity_assumption=16,full_FTQ_reachability_proved=False,physical_coordinate_enumeration=False)


PROGRAMS=tuple(Program(f,r,c) for f in FATES for r in REVISIONS for c in COUNTERS)
