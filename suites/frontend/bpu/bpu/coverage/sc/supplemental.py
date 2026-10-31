"""suites.frontend.bpu.bpu.coverage.sc.supplemental components."""

from itertools import combinations
from math import prod
from toffee import Bin
from toffee import CoverGroupDef
from toffee import CoverPointDef
from toffee import CrossDef


def matrix_coverage():
    axes = dict(bank=(0, 1), row=(0, 1), pair=tuple(f'{a}_{b}' for a, b in combinations((4, 5, 6, 7), 2)),
                order=('forward', 'reverse'), lifecycle=('dirty_merge', 'clean_reactivate'))
    points = tuple(CoverPointDef(name, {str(value): Bin.values(value) for value in values})
                   for name, values in axes.items())
    return CoverGroupDef('bpu_sc_masked_feedback', points,
        crosses=(CrossDef('qualified_mask_lifecycle_matrix', tuple(axes),
                          max_auto_bins=prod(map(len, axes.values()))),)).instantiate('kunminghu_v3.bpu.sc_masked_feedback')
