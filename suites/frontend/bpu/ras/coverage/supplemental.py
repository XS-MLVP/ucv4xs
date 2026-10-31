"""RAS requirements; coverage definitions never import concrete test stimuli."""
from suites.frontend.bpu.models.configuration import *

from suites.frontend.bpu.coverage.exports import write_functional_coverage
from suites.frontend.bpu.runtime.artifacts import output_path
from toffee import Bin
from toffee import CoverGroupDef
from toffee import CoverPointDef
from toffee import CoverageDatabase
from toffee import CrossDef


ADJACENT_SCENARIOS = tuple(
    f'{profile}-depth{depth}-{kind}'
    for depth in range(1, 5)
    for kind in ('distinct', 'repeat')
    for profile in ('nested', 'alternate', 'turnaround')
) + tuple(f'saturated-repeat{count}' for count in (9, 10, 12))

RETIREMENT_GAP_CONTRACTS = ('genuine-metadata', 'omitted-call-retirement', 'distance-threshold',
    'push-or-pop-priority', 'complete-retained-state', 'continued-call-return')


def ras_retirement_gap_coverage_model():
    return _cross('retirement_gap', dict(epoch=('same', 'cross'),
        kind=('threshold-hold', 'gap-reclaim', 'push-priority'), contract=RETIREMENT_GAP_CONTRACTS))


def ras_committed_cells_coverage_model():
    return _cross('committed_cells', dict(slot=range(RAS_GROUPS), mode=('normal', 'saturated')))


def ras_adjacent_coverage_model():
    return _cross('adjacent_operations', dict(scenario=ADJACENT_SCENARIOS))


def ras_redirect_redo_coverage_model():
    return _cross('redirect_redo', dict(storage=('inflight', 'committed'), counter=(0, 3, 7),
        redo=('call-same', 'call-distinct-positive', 'call-distinct-negative', 'return')))


def _cross(name, axes):
    points = tuple(CoverPointDef(axis, {str(value): Bin.values(value) for value in values})
        for axis, values in axes.items())
    crosses = (CrossDef('all_dimensions', tuple(axes)),) if len(axes) > 1 else ()
    return CoverGroupDef('ras_' + name, points, crosses=crosses).instantiate('kunminghu_v3.ras.' + name)


def write_ras_scenario_coverage(coverage, root, name):
    if name not in ('committed-cells', 'adjacent-operations', 'redirect-redo', 'retirement-gap'):
        raise ValueError('unsupported RAS scenario coverage file')
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / 'results/ras' / f'functional-coverage-{name}.json'))
