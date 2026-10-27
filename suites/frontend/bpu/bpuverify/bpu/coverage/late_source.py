"""Late-feedback ownership at the composed BPU, not physical coverage bins."""
from toffee import Bin
from toffee import CoverGroupDef
from toffee import CoverPointDef
from toffee import CoverageDatabase

from bpuverify.common.coverage.exports import write_functional_coverage

RULES = (
    'unpublished-original-observed',
    'late-feedback-does-not-learn-ittage',
    'fresh-consumer-remains-cold',
)


def late_source_coverage(status):
    if status not in ('reached', 'checked'):
        raise ValueError('declared late-source evidence role required')
    return CoverGroupDef('bpu_late_source_v1', (
        CoverPointDef('obligation', {rule: Bin.values(rule) for rule in RULES}),
    )).instantiate('kunminghu_v3.bpu.late-source.' + status)


class LateSourceCoverage:
    def __init__(self):
        self.groups = {status: late_source_coverage(status)
                       for status in ('reached', 'checked')}

    def record(self, status, rule, **witness):
        if status not in self.groups or rule not in RULES:
            raise ValueError('unknown late-source evidence role or obligation')
        self.groups[status].sample(dict(obligation=rule), metadata=witness)

    def write(self, output):
        write_functional_coverage(
            CoverageDatabase(self.groups.values()),
            output / 'functional-coverage-late-source.json',
        )
