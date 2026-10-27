"""Public use qualification while the RAS enable is withdrawn."""
from toffee import Bin
from toffee import CoverGroupDef
from toffee import CoverPointDef
from toffee import CoverageDatabase

from bpuverify.common.coverage.exports import write_functional_coverage

RULES = (
    'armed-target-published',
    'disabled-target-suppressed',
    're-enabled-target-retained',
)


def gate_coverage(status):
    if status not in ('reached', 'checked'):
        raise ValueError('declared enable-gate role required')
    return CoverGroupDef('uras_enable_gate_v1', (
        CoverPointDef('obligation', {rule: Bin.values(rule) for rule in RULES}),
    )).instantiate('kunminghu_v3.uras.enable-gate.' + status,
        contract='armed return target -> disabled public suppression -> re-enabled retention')


class EnableGateCoverage:
    def __init__(self):
        self.groups = {status: gate_coverage(status) for status in ('reached', 'checked')}

    def record(self, status, rule, **witness):
        if status not in self.groups or rule not in RULES:
            raise ValueError('unknown enable-gate role or obligation')
        self.groups[status].sample(dict(obligation=rule), metadata=witness)

    def write(self, output):
        write_functional_coverage(
            CoverageDatabase(self.groups.values()),
            output / 'functional-coverage-enable-gate.json',
        )
