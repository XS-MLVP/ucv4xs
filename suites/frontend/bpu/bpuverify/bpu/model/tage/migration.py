"""Three real path identities and one delayed, non-reread provider outcome.

The path deltas are two nullspace vectors of the seven-bit T3 row fold.
They preserve the row, not the tag. No DUT address/proposal or state chooses
the contexts. Controlled semantic allocation uses the independent generator.
"""
from dataclasses import dataclass
from bpuverify.bpu.model.tage.forwarding import PC

POSITION,TARGET=4,PC+0x200
PATHS=dict(blocker=PC,original=PC^0x648,newcomer=PC^0xad8)


@dataclass(frozen=True,slots=True)
class LearningIntent:
    label:str
    context:str
    taken:bool
    wrong:bool
    expected:tuple
    owner:tuple|None=None
    tage_enabled:bool=True


def preparation(original_way=1):
    """Hand-derived (Main counter, provider(table,way,counter,useful)) effects."""
    if type(original_way) is not int or original_way not in (0,1):raise ValueError('original owner must be one of the two ways')
    first,second=('blocker','original') if original_way else ('original','blocker')
    yield LearningIntent('main','blocker',True,True,(2,None))
    yield LearningIntent('base-low-1','blocker',False,True,(1,None),tage_enabled=False)
    yield LearningIntent('base-low-2','blocker',False,False,(0,None),tage_enabled=False)
    yield LearningIntent(f'{first}-install',first,True,True,(1,(3,0,4,0)),owner=(3,0))
    yield LearningIntent('base-high-1','blocker',True,True,(2,None),tage_enabled=False)
    yield LearningIntent('base-high-2','blocker',True,False,(3,None),tage_enabled=False)
    for counter in range(5,6 if first=='original' else 8):
        yield LearningIntent('original' if first=='original' else f'blocker-{counter}',first,True,False,(3,(3,0,counter,0)))
    yield LearningIntent('base-low-for-second-1',second,False,True,(2,None),tage_enabled=False)
    yield LearningIntent('base-low-for-second-2',second,False,True,(1,None),tage_enabled=False)
    yield LearningIntent(f'{second}-install',second,True,True,(2,(3,1,4,0)),owner=(3,1))
    for counter in range(5,6 if second=='original' else 8):
        yield LearningIntent('original' if second=='original' else f'blocker-{counter}',second,True,False,(3,(3,1,counter,0)))
    yield LearningIntent('weaken','original',False,True,(2,(3,original_way,4,0)))
    yield LearningIntent('base-low-before-replace','newcomer',False,True,(1,None),tage_enabled=False)
    yield LearningIntent('newcomer-install','newcomer',True,True,(2,(3,original_way,4,0)),owner=(3,original_way))
    yield LearningIntent('base-low-before-protect','newcomer',False,True,(1,None),tage_enabled=False)
    yield LearningIntent('newcomer-protect','newcomer',True,True,(2,(3,original_way,5,1)))
    yield LearningIntent('base-low-before-migrate','original',False,True,(1,None),tage_enabled=False)
    yield LearningIntent('migrated','original',True,True,(2,(3,1-original_way,4,0)),owner=(3,1-original_way))
