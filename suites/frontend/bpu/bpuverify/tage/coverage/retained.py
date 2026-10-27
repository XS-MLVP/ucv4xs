"""Requirement bins for cross-owner counter forwarding, sampled after checks."""

from bpuverify.common.coverage.exports import write_functional_coverage
from bpuverify.common.env.artifacts import output_path
from toffee import Bin
from toffee import CoverGroupDef
from toffee import CoverPointDef
from toffee import CoverageDatabase
from toffee import CrossDef


def tage_retained_owner_coverage_model():
    axes = dict(bank=range(4), origin=range(2), depth=range(4),
                mode=('pending', 'clean'), phase=('native', 'forward', 'reverse'))
    points = tuple(CoverPointDef(name, {str(value):Bin.values(value) for value in values})
                   for name, values in axes.items())
    return CoverGroupDef('tage_retained_owner', points,
        crosses=(CrossDef('all_dimensions', tuple(axes)),)
    ).instantiate('kunminghu_v3.tage.retained_owner')


def write_tage_retained_owner_coverage(coverage, root):
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root/'results/tage'/'functional-coverage-retained-owner.json'))
