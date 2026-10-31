"""Semantic program completion, separate from reached stimulus and pytest."""
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase

from suites.frontend.bpu.coverage.exports import write_functional_coverage
from suites.frontend.bpu.sc.model.neutral_boundary import PROFILES, RULES


def lifetime_coverage(status):
    if status not in ('reached', 'checked'):
        raise ValueError('neutral-boundary coverage needs reached or checked')
    keys = tuple(boundary + '.' + placement + '.' + rule
                 for boundary, placement in PROFILES for rule in RULES)
    return CoverGroupDef('sc_neutral_boundary_v1', (
        CoverPointDef('obligation', {key: Bin.values(key) for key in keys}),
    )).instantiate('kunminghu_v3.sc.neutral-boundary.' + status,
        contract='original qualified opposite votes at signed endpoints -> neutral shared experience -> exact fresh five-family recovery')


class NeutralBoundaryCoverage:
    def __init__(self):
        self.groups = {status: lifetime_coverage(status) for status in ('reached', 'checked')}
        self.evidence = None

    def record(self, status, label, rule, **witness):
        if rule not in RULES or label not in {a + '.' + b for a, b in PROFILES}:
            raise ValueError('unknown shared-neutrality program or obligation')
        self.groups[status].sample(dict(obligation=label + '.' + rule), metadata=witness)

    def write(self, output):
        write_functional_coverage(CoverageDatabase(self.groups.values()),
                                  output / 'functional-coverage-neutral-boundary.json')

    def attach_evidence(self, properties):
        if self.evidence is not None:
            import json
            properties.append(('semantic_sc_neutral_boundary', json.dumps(self.evidence, ensure_ascii=False)))
