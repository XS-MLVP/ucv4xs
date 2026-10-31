"""Functional coverage for virtual public-boundary system contracts."""
from toffee import Bin, CoverGroupDef, CoverPointDef


class VirtualSystemCoverage:
    def __init__(self):
        self.group = CoverGroupDef('vagq_virtual_system_contract_v1', (
            CoverPointDef('scenario', {
                name: Bin.values(name) for name in (
                    'response-reorder', 'late-response-redirect',
                    'vrf-merge', 'precise-restart', 'ordered-sq',
                    'capacity-reuse',
                )
            }),
            CoverPointDef('virtual_outcome', {
                name: Bin.values(name) for name in (
                    'contract-pass', 'contract-violation',
                )
            }),
            CoverPointDef('isa_result', {
                name: Bin.values(name) for name in (
                    'pass-local', 'counterexample', 'boundary',
                )
            }),
            CoverPointDef('scope', {
                name: Bin.values(name) for name in (
                    'public-boundary-contract', 'whole-chip-unobservable',
                )
            }),
        )).instantiate(
            'vagq.virtual_system.contract.checked',
            contract='Independent event-driven public-boundary system contract/v1',
        )

    def sample(self, *, scenario, virtual_outcome, isa_result, scope):
        self.group.sample({
            'scenario': scenario,
            'virtual_outcome': virtual_outcome,
            'isa_result': isa_result,
            'scope': scope,
        })


VIRTUAL_COVERAGE = VirtualSystemCoverage()
