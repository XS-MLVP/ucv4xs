"""Stable semantic requirements, separate offered and successfully checked credit."""

from suites.frontend.bpu.coverage.exports import write_functional_coverage
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase
from suites.frontend.bpu.utage.coverage.supplemental import utage_useful_allocation_coverage_model, utage_useful_update_coverage_model


BOUNDARY_RULES = ('split-source', 'short-allocation', 'useful-positive-saturation',
    'base-agreement-hold', 'adjacent-negative-chain', 'useful-zero-hold',
    'long-provider-selected', 'interleaved-context-association')
TYPE_RULES = ('resolved-direct-same-position', 'resolved-indirect-same-position')


def semantic_coverage(family, status):
    rules = BOUNDARY_RULES if family == 'boundary' else TYPE_RULES if family == 'resolved-type' else None
    if rules is None or status not in ('reached', 'checked'):
        raise ValueError('unknown UTAGE semantic coverage family or status')
    return CoverGroupDef(f'utage_semantic_{family}_v1', (
        CoverPointDef('rule', {rule: Bin.values(rule) for rule in rules}),
    )).instantiate(f'kunminghu_v3.utage.semantic.{family}.{status}',
        contract='observed public offer/source -> independent table/useful comparison -> semantic endpoint')


class SemanticCoverage:
    def __init__(self, family):
        self.family = family
        self.groups = {status: semantic_coverage(family, status) for status in ('reached', 'checked')}
        self.physical_allocation = utage_useful_allocation_coverage_model() if family == 'boundary' else None
        self.physical_update = utage_useful_update_coverage_model() if family == 'boundary' else None

    def record(self, status, rule, **witness):
        self.groups[status].sample(dict(rule=rule), metadata=dict(rule=rule, **witness))

    def write(self, output):
        groups = list(self.groups.values())
        if self.physical_allocation is not None:
            groups.extend((self.physical_allocation, self.physical_update))
        write_functional_coverage(CoverageDatabase(groups), output / f'functional-coverage-semantic-{self.family}.json')
