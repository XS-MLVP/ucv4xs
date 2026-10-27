"""Communication and input order are semantic parameters, not bank sweeps."""
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase
from bpuverify.common.coverage.exports import write_functional_coverage
from bpuverify.mbtb.model.full_capacity_learning import MODES, ORDERS, RULES, POSITION_RELATIONS


def obligation(mode, order, rule, relation):
    # Keep the original same-position bin names and meanings intact.
    middle = '' if relation == 'same-position' else relation + '.'
    return f'{mode}.{order}.{middle}{rule}'


class FullCapacityCoverage:
    def __init__(self, mode, order, *, position_relation='same-position'):
        if mode not in MODES or order not in ORDERS or position_relation not in POSITION_RELATIONS:
            raise ValueError('unknown semantic coverage case')
        self.mode, self.order, self.position_relation = mode, order, position_relation
        self.groups = {status: CoverGroupDef('mbtb_full_capacity_learning_v2', (
            CoverPointDef('obligation', {obligation(m, o, r, relation): Bin.values(obligation(m, o, r, relation))
                for m in MODES for o in ORDERS for relation in POSITION_RELATIONS for r in RULES}),
        )).instantiate('kunminghu_v3.mbtb.full-capacity-learning.' + status)
            for status in ('reached', 'checked')}

    def record(self, status, rule, **witness):
        self.groups[status].sample(dict(obligation=obligation(self.mode, self.order, rule, self.position_relation)),
            metadata=dict(position_relation=self.position_relation, **witness))

    def write(self, output):
        write_functional_coverage(CoverageDatabase(self.groups.values()),
                                  output / 'functional-coverage-full-capacity-learning.json')
