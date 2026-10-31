"""Required address matrices, including currently defect-blocked combinations."""

from suites.frontend.bpu.coverage.exports import write_functional_coverage
from suites.frontend.bpu.runtime.artifacts import output_path
from math import prod
from toffee import Bin
from toffee import CoverGroupDef
from toffee import CoverPointDef
from toffee import CoverageDatabase
from toffee import CrossDef


MODES = ('serial', 'adjacent')
UPDATE_ROLES = ('increase', 'increase_hold', 'decrease', 'decrease_hold')


def _matrix(name, axes):
    points = tuple(CoverPointDef(axis, {str(value): Bin.values(value) for value in values})
                   for axis, values in axes.items())
    return CoverGroupDef('utage_' + name, points,
        crosses=(CrossDef('all_dimensions', tuple(axes), max_auto_bins=prod(len(values) for values in axes.values())),)).instantiate('kunminghu_v3.utage.' + name)


def utage_useful_allocation_coverage_model():
    return _matrix('useful_allocation_routes', dict(mode=MODES, table=range(2), index=range(512)))


def utage_useful_update_coverage_model():
    return _matrix('useful_update_routes', dict(mode=MODES, table=range(2), index=range(512), role=UPDATE_ROLES))


def utage_partial_wrap_coverage_model():
    return _matrix('partial_shadow_wrap', dict(mode=MODES, bank=range(4),
        phase=('old_slot2_payload', 'all_retained_neighbors')))


def write_utage_address_coverage(coverage, root, name):
    if name not in ('useful-allocation', 'useful-update', 'partial-shadow-wrap'):
        raise ValueError('unsupported MicroTAGE address coverage artifact')
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / 'results/utage' / f'functional-coverage-{name}.json'))
