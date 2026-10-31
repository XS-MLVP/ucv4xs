"""Semantic target-feedback coverage, independent of physical bank count."""

from suites.frontend.bpu.coverage.exports import write_functional_coverage
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase
from suites.frontend.bpu.runtime.artifacts import output_path

OPERATIONS = ('allocate', 'increment', 'decrement', 'high_hold', 'low_hold',
              'provider_and_alternate', 'alternate_selected', 'alternate_penalty',
              'zero_confidence_target_write', 'public_target_checked')

DIRECTORY_RULES = {
    'allocation': ('pc-region-bypass', 'free-entry', 'reuse-before-full', 'reuse-at-full', 'PLRU-replacement'),
    'consumption': ('pc-region', 'resident-pointer', 'replaced-pointer'),
}


def directory_coverage(family, status):
    if family not in DIRECTORY_RULES or status not in ('reached', 'checked'):
        raise ValueError('unknown ITTAGE directory event coverage scope')
    return CoverGroupDef(f'ittage_region_{family}_events_v1', (
        CoverPointDef('rule', {name: Bin.values(name) for name in DIRECTORY_RULES[family]}),
    )).instantiate(f'kunminghu_v3.bpu.ittage_region_directory.{family}.{status}',
        contract='genuine source -> independent reset-derived directory -> complete commit or public consumer')


class DirectoryCoverage:
    def __init__(self):
        self.groups = {(family, status): directory_coverage(family, status)
            for family in DIRECTORY_RULES for status in ('reached', 'checked')}

    def sample(self, family, status, event):
        self.groups[family, status].sample(dict(rule=event['rule']), metadata=event)

    def require(self):
        for group in self.groups.values():
            group.assert_coverage(100)

    def write(self, output):
        write_functional_coverage(CoverageDatabase(list(self.groups.values())), output / 'functional-coverage-ittage-region-directory.json')


def feedback_coverage():
    return CoverGroupDef('integrated_ittage_target_feedback', (
        CoverPointDef('operation', {name: Bin.values(name) for name in OPERATIONS}),
    )).instantiate('kunminghu_v3.bpu.ittage_target_feedback')


def write_feedback_coverage(coverage, root):
    write_functional_coverage(CoverageDatabase([coverage]), output_path(
        root / 'results/bpu/functional-coverage-ittage-target-feedback.json'))
