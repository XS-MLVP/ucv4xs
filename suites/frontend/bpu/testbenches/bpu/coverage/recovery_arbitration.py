"""Paired obligations for complete original recovery lifetimes."""
from toffee import Bin,CoverGroupDef,CoverPointDef,CoverageDatabase

RULES=('real-old-source','distinct-younger-path','declared-arbitration-window',
       'backend-wins','younger-cancelled','fresh-history-consumer','immutable-sources')
PROFILES=tuple(mode+'.'+direction for mode in ('collision','after-repair') for direction in ('taken','not-taken'))


class RecoveryCoverage:
    def __init__(self,program):
        self.program=program
        self.groups={status:CoverGroupDef('bpu_original_recovery_arbitration_v1',(
            CoverPointDef('obligation',{profile+'.'+rule:Bin.values(profile+'.'+rule)
                for profile in PROFILES for rule in RULES}),
        )).instantiate('kunminghu_v3.bpu.original-recovery-arbitration.'+status)
            for status in ('reached','checked')}

    def database(self):return CoverageDatabase(self.groups.values())
