"""Prediction cancellation and already accepted learning are different lifetimes."""
from dataclasses import dataclass
from suites.frontend.bpu.bpu.model.main_original_order import Program as OriginalProgram,PC,STREAM_PC,EARLIER,LATER,INITIAL_TARGET,TARGETS

FATES=('source-preserved','source-cancelled')
MOMENTS=('publication-overlap','retained-record')
RULES=('real-distinct-originals','input-qualified-before-recovery','declared-source-fate',
    'declared-learning-recovery-overlap','accepted-copy-retained-after-recovery',
    'complete-entry-and-direction-services','fresh-original-branch-target',
    'fresh-unexecuted-sibling','immutable-originals')


@dataclass(frozen=True,slots=True)
class Program:
    fate:str
    moment:str

    def __post_init__(self):
        if type(self.fate) is not str or self.fate not in FATES:raise ValueError('declared original-source fate required')
        if type(self.moment) is not str or self.moment not in MOMENTS:raise ValueError('declared learning/recovery boundary required')

    @property
    def label(self):return self.fate+'.'+self.moment
    @property
    def cancelled(self):return self.fate=='source-cancelled'
    @property
    def restore_index(self):return 0 if self.cancelled else 1
    @property
    def sibling_counter(self):return 1
    @property
    def target(self):return TARGETS[0]
    @property
    def original(self):return OriginalProgram('old-then-young','retained-under-reads',self.sibling_counter)
    @property
    def owner(self):return self.original.owner
    @property
    def effect(self):return self.original.effect(0)
    @property
    def direction(self):return self.original.direction
    @property
    def services(self):return (self.effect,)

    def state(self):
        return dict(fate=self.fate,moment=self.moment,restore_index=self.restore_index,
            target=self.target,sibling_counter=self.sibling_counter,expected_source_cancelled=self.cancelled,
            capacity_assumption=16,simultaneous_input_and_external_recovery=False,
            full_FTQ_reachability_proved=False,physical_coordinate_enumeration=False)
