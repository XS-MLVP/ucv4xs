"""Original-snapshot qualification for late indirect-target feedback."""
from pathlib import Path

from toffee import Bin
from toffee import CoverGroupDef
from toffee import CoverPointDef
from toffee import CoverageDatabase

from suites.frontend.bpu.coverage.exports import write_functional_coverage
from suites.frontend.bpu.runtime.artifacts import output_path

RULES = (
    'unpublished-original-observed',
    'late-feedback-does-not-learn',
    'served-control-learns',
)


def late_source_coverage(status):
    if status not in ('reached', 'checked'):
        raise ValueError('declared late-source evidence role required')
    return CoverGroupDef('ittage_late_source_v1', (
        CoverPointDef('obligation', {rule: Bin.values(rule) for rule in RULES}),
    )).instantiate('kunminghu_v3.ittage.late-source.' + status)


class LateSourceCoverage:
    def __init__(self):
        self.groups = {status: late_source_coverage(status)
                       for status in ('reached', 'checked')}

    def record(self, status, rule, **witness):
        if status not in self.groups or rule not in RULES:
            raise ValueError('unknown late-source evidence role or obligation')
        self.groups[status].sample(dict(obligation=rule), metadata=witness)

    def write(self, root: Path):
        write_functional_coverage(
            CoverageDatabase(self.groups.values()),
            output_path(Path(root) / 'results' / 'ittage' /
                        'functional-coverage-late-source.json'),
        )
