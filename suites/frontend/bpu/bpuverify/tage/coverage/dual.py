"""Independent dual-write requirements, sampled only after complete comparisons."""

from bpuverify.common.coverage.exports import write_functional_coverage
from bpuverify.common.env.artifacts import output_path
from toffee import Bin
from toffee import CoverGroupDef
from toffee import CoverPointDef
from toffee import CoverageDatabase
from toffee import CrossDef


DUAL_MODES = ('own_pending', 'own_clean', 'cross_pending', 'cross_clean',
              'companion_dirty_hit', 'companion_clean_hit',
              'companion_miss', 'companion_miss_saturated')


def tage_dual_shadow_coverage_model():
    axes = dict(bank=range(4), depth=range(4), mode=DUAL_MODES,
                phase=('native', 'forward', 'reverse'))
    points = tuple(CoverPointDef(name, {str(value): Bin.values(value) for value in values})
                   for name, values in axes.items())
    return CoverGroupDef('tage_dual_shadow', points,
        crosses=(CrossDef('all_dimensions', tuple(axes)),)
    ).instantiate('kunminghu_v3.tage.dual_shadow')


def write_tage_dual_shadow_coverage(coverage, root):
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / 'results/tage/functional-coverage-dual-shadow.json'))
