"""Human scenarios and execution-prefix outcomes, not physical table walks."""
from dataclasses import dataclass

from bpuverify.bpu.model.selection import Kind

PC=0x40000800
VIA=PC+0x100
CONDITION,INDIRECT=2,10
CONDITION_TARGET,INDIRECT_TARGET,MAIN_WRONG=PC+0x200,PC+0x400,PC+0x600
MODES=('conditional-opens-indirect','conditional-suppresses-indirect')
RULES=('same-original-window','both-independent-read-stages','both-late-sources-learned',
    'main-only-learning-preserves-late-sources','two-opposed-base-predictions',
    'original-target-selected-only-for-indirect','complete-executed-prefix-feedback',
    'fresh-selected-consumer','same-pc-different-original-history','immutable-original-snapshots')


@dataclass(frozen=True)
class BranchOutcome:
    position:int
    target:int
    kind:Kind
    taken:bool
    wrong:bool


@dataclass(frozen=True)
class Step:
    name:str
    branches:tuple=()
    enable:bool|None=None


def condition(taken,wrong):return BranchOutcome(CONDITION,CONDITION_TARGET,Kind.CONDITIONAL,taken,wrong)
def indirect(target=INDIRECT_TARGET,wrong=False):return BranchOutcome(INDIRECT,target,Kind.INDIRECT,True,wrong)


@dataclass(frozen=True)
class Program:
    mode:str

    def __post_init__(self):
        if self.mode not in MODES:raise ValueError('unknown joint late-source scenario')

    def establishment(self):
        return (Step('discover-indirect',(indirect(wrong=True),)),
            Step('discover-earlier-condition',(condition(True,True),)),
            Step('learn-opposed-direction',(condition(False,True),indirect())),
            Step('strengthen-opposed-direction',(condition(False,False),indirect())),
            Step('disable-late-learning',enable=False),
            Step('change-only-main-target',(condition(False,False),indirect(MAIN_WRONG,True))),
            Step('restore-only-main-direction-weak',(condition(True,True),)),
            Step('restore-only-main-direction-taken',(condition(True,True),)),
            Step('reenable-original-late-sources',enable=True))

    def state(self):
        return dict(mode=self.mode,pc=PC,condition_position=CONDITION,indirect_position=INDIRECT,
            condition_target=CONDITION_TARGET,indirect_target=INDIRECT_TARGET,opposing_main_target=MAIN_WRONG,
            physical_enumeration=False)
