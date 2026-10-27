"""A compared same-boundary cohort, never acceptance-only functional credit."""
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase
from bpuverify.common.coverage.exports import write_functional_coverage
from bpuverify.bpu.model.tage.service_relearning import PROGRAMS

RULES = ('independent-original-predictions', 'independent-pending-learning',
    'fresh-old-storage-consumers', 'actual-executed-feedback-prefix',
    'old-service-meets-new-learning', 'new-version-survives-old-completion',
    'unexecuted-sibling-and-neighbor-preserved', 'fresh-mixed-storage-consumers',
    'all-remaining-versions-actually-serviced', 'final-consumers-and-immutable-originals')


def lifetime_coverage(status):
    if status not in ('reached', 'checked'): raise ValueError('declared cohort lifecycle required')
    bins = {p.name+'.'+rule: Bin.values(p.name+'.'+rule) for p in PROGRAMS for rule in RULES}
    return CoverGroupDef('bpu_service_relearning_v1', (CoverPointDef('obligation', bins),)).instantiate(
        'kunminghu_v3.bpu.service-relearning.'+status)


class Coverage:
    def __init__(self, program):
        if program not in PROGRAMS: raise ValueError('declared learning coexistence program required')
        self.program = program
        self.groups = {s: lifetime_coverage(s) for s in ('reached', 'checked')}
        self.seen = {}
        self.closed = False

    def record(self, rule, **witness):
        if self.closed or rule not in RULES: raise ValueError('open declared learning obligation required')
        if rule in self.seen: raise AssertionError('semantic obligation recorded twice: '+rule)
        self.seen[rule] = witness
        self.groups['reached'].sample(dict(obligation=self.program.name+'.'+rule), metadata=witness)

    def finish(self):
        if self.closed or set(self.seen) != set(RULES):
            raise AssertionError(f'incomplete same-boundary cohort: {sorted(self.seen)}')
        for rule, witness in self.seen.items():
            self.groups['checked'].sample(dict(obligation=self.program.name+'.'+rule), metadata=witness)
        self.closed = True

    def write(self, output):
        write_functional_coverage(CoverageDatabase(self.groups.values()),
            output/'functional-coverage-service-relearning.json')
