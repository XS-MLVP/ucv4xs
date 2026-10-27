"""A complete replacement obligation is more than reaching a full buffer."""
from toffee import Bin,CoverGroupDef,CoverPointDef,CoverageDatabase
from bpuverify.common.coverage.exports import write_functional_coverage
from bpuverify.bpu.model.tage.retouch_replacement import PROGRAMS

RULES=('five-normal-history-source-profiles-qualified','owned-inputs-and-original-history-qualified',
       'actual-full-capacity-before-late-learning','retouches-compose-current-confidence',
       'new-history-replaces-only-access-policy-victim','auxiliary-main-updates-accepted-without-loss',
       'five-blocked-consumers-still-see-old-storage','eight-complete-survivor-services',
       'all-five-final-consumers-and-unserviced-victim','all-original-source-snapshots-preserved')


class RetouchReplacementCoverage:
    rules=RULES
    programs=PROGRAMS
    namespace='retouch-replacement'
    filename='functional-coverage-retouch-replacement.json'
    def __init__(self,program):
        if program not in self.programs:raise ValueError('unknown retouch replacement program')
        self.groups={role:CoverGroupDef('bpu_retouch_replacement_v1',(
            CoverPointDef('rule',{r:Bin.values(r) for r in RULES}),)).instantiate(
                f'kunminghu_v3.bpu.{self.namespace}.{program.name}.{role}') for role in ('reached','checked')}

    def record(self,role,rule,**witness):
        if role not in self.groups or rule not in RULES:raise ValueError('unknown retouch obligation')
        self.groups[role].sample(dict(rule=rule),metadata=witness)

    def write(self,output):
        write_functional_coverage(CoverageDatabase(self.groups.values()),
                                  output/self.filename)
