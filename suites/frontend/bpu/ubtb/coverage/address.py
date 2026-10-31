"""Address-semantic consumers, not a physical address/bank enumeration."""
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase

from suites.frontend.bpu.coverage.exports import write_functional_coverage
from suites.frontend.bpu.runtime.artifacts import output_path
from suites.frontend.bpu.runtime.paths import REPO_ROOT


RULES = ('instruction-byte-bit1', 'distinct-tag-byte-bit22', 'stored-target-byte-bit22',
         'eight-mib-forward-wrap', 'eight-mib-backward-wrap', 'highest-unguarded-byte-region')


def address_coverage(status):
    if status not in ('reached', 'checked'):
        raise ValueError('unknown address coverage status')
    return CoverGroupDef('ubtb_byte_address_semantics_v1', (
        CoverPointDef('rule', {rule: Bin.values(rule) for rule in RULES}),
    )).instantiate(f'kunminghu_v3.ubtb.byte-address.{status}',
        contract='accepted byte-domain lookup -> independently expected identity/target -> complete fresh consumers')


class AddressCoverage:
    def __init__(self):
        self.groups = {status: address_coverage(status) for status in ('reached', 'checked')}

    def record(self, status, rule):
        self.groups[status].sample(dict(rule=rule))

    def write(self):
        write_functional_coverage(CoverageDatabase(self.groups.values()),
            output_path(REPO_ROOT / 'results' / 'ubtb' / 'functional-coverage-byte-address.json'))
