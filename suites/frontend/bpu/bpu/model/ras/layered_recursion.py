"""Expanded logical calls define the oracle; storage positions do not."""
from dataclasses import dataclass
from suites.frontend.bpu.ras.model.model import CommittedStack, advance

ROOT = 0x40020000
LAYERS = (ROOT + 0x60, ROOT + 0xC0, ROOT + 0x120)
ROOT_RETURN = ROOT + 16
POSITION = 15
PROFILES = (8, 10)
RULES = ('distinct-recursive-layer-sources', 'older-calls-retired-before-growth',
    'owned-target-corrections', 'no-duplicate-redone-call', 'all-logical-calls-retained',
    'innermost-repeat-boundary', 'complete-mixed-pc-return-chain',
    'outer-return-identities-restored', 'outer-repeat-counts-preserved',
    'every-live-operation-retired-once', 'complete-sentinel-state-restored', 'immutable-originals')


@dataclass(frozen=True)
class Program:
    inner_calls: int

    def __post_init__(self):
        if type(self.inner_calls) is not int or self.inner_calls not in PROFILES:
            raise ValueError('innermost full group or nonzero split group required')

    @property
    def counts(self):
        return (3, 2, self.inner_calls)

    def call_addresses(self, layers=3):
        if type(layers) is not int or not 0 <= layers <= len(LAYERS):
            raise ValueError('unknown recursive layer prefix')
        return (ROOT_RETURN,) + tuple(pc + 16 for pc, count in zip(LAYERS[:layers], self.counts[:layers])
                                      for _ in range(count))

    @property
    def return_targets(self):
        return self.call_addresses()[::-1]

    @property
    def return_pcs(self):
        return (LAYERS[-1] + 16,) + self.return_targets[:-1]

    def committed(self, *, layers=3, returned=0):
        addresses = self.call_addresses(layers)
        if type(returned) is not int or not 0 <= returned <= len(addresses):
            raise ValueError('return cannot consume an absent logical caller')
        state = CommittedStack()
        for address in addresses:
            state = advance(state, 2, address=address)
        for _ in range(returned):
            state = advance(state, 1)
        return state

    def sites(self):
        # Recursive calls are indirect throughout: the final dynamic target
        # legitimately changes to the next recursive body or the return body.
        return ((ROOT, LAYERS[0], 2, 2),) + tuple((pc, pc, 3, 2) for pc in LAYERS) + tuple(
            (pc + 16, ROOT + 0xF000, 3, 1) for pc in LAYERS) + (
            (ROOT_RETURN, ROOT_RETURN, 2, 0),)

    def state(self):
        return dict(inner_calls=self.inner_calls, counts=self.counts, layer_pcs=LAYERS,
            root_return=ROOT_RETURN, logical_calls=len(self.call_addresses()),
            expected_return_pcs=self.return_pcs, expected_return_targets=self.return_targets,
            physical_coordinate_enumeration=False)
