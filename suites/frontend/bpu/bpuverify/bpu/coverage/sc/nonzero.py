"""bpuverify.bpu.coverage.sc.nonzero components."""

from bpuverify.common.coverage.exports import write_functional_coverage

from bpuverify.common.env.artifacts import output_path
from toffee import Bin
from toffee import CoverGroupDef
from toffee import CoverPointDef
from toffee import CoverageDatabase
from toffee import CrossDef
from bpuverify.bpu.model.sc.model import TABLES


def coverage():
    axes = dict(bank=(0, 1), direction=('forward', 'backward'), table=TABLES, feedback=(0, 1))
    return CoverGroupDef('sc_real_nonzero_common_history',
        tuple(CoverPointDef(key, {str(value): Bin.values(value) for value in values}) for key, values in axes.items()),
        crosses=(CrossDef('bank_direction_table_feedback', tuple(axes), max_auto_bins=40),)
        ).instantiate('kunminghu_v3.bpu.sc_real_nonzero_common_history')


def save(group, output):
    write_functional_coverage(CoverageDatabase((group,)), output_path(output / 'functional-coverage-real-nonzero-history.json'))
