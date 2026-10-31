"""End-to-end cohort credit waits for every service and fresh consumer."""
from toffee import Bin,CoverGroupDef,CoverPointDef,CoverageDatabase
from suites.frontend.bpu.coverage.exports import write_functional_coverage
from suites.frontend.bpu.bpu.model.tage.shared_saturation import PROGRAMS

RULES=('all-owner-capacities-occupied','full-hit-keeps-logical-ownership',
    'all-eight-latest-results-retained','fresh-old-storage-consumer',
    'release-retires-eight-results-once','all-four-histories-consume-commits',
    'distinct-interior-originals','each-history-reaches-and-holds-both-bounds','original-snapshots-unchanged')


def lifetime_coverage(status):
    if status not in ('reached','checked'):raise ValueError('declared lifecycle status required')
    bins={p.name+'.'+rule:Bin.values(p.name+'.'+rule) for p in PROGRAMS for rule in RULES}
    return CoverGroupDef('bpu_shared_saturation_v1',(CoverPointDef('obligation',bins),)).instantiate(
        'kunminghu_v3.bpu.shared-saturation.'+status)


class Coverage:
    rules=RULES

    def __init__(self,program):
        if program not in PROGRAMS:raise ValueError('declared shared learning program required')
        self.program=program;self.groups={s:lifetime_coverage(s) for s in ('reached','checked')}
        self.seen={};self.compared={}

    def record(self,status,rule,tick):
        if status not in self.groups or rule not in RULES:raise ValueError('declared shared learning obligation required')
        if status=='checked':self.compared[rule]=tick;return
        if rule not in self.seen:
            self.seen[rule]=tick
            self.groups['reached'].sample(dict(obligation=self.program.name+'.'+rule),metadata=dict(tick=tick))

    def finish(self):
        if set(self.seen)!=set(RULES) or set(self.compared)!=set(RULES):
            raise AssertionError(f'incomplete shared learning cohort: reached={sorted(self.seen)}, compared={sorted(self.compared)}')
        for rule,tick in self.compared.items():
            self.groups['checked'].sample(dict(obligation=self.program.name+'.'+rule),metadata=dict(tick=tick))

    def write(self,output):
        write_functional_coverage(CoverageDatabase(self.groups.values()),output/'functional-coverage-shared-saturation.json')
