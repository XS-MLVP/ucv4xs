"""bpuverify.bpu.coverage.sc.history components."""

from bpuverify.common.coverage.exports import write_functional_coverage

from bpuverify.common.env.artifacts import output_path
from toffee import Bin
from toffee import CoverGroupDef
from toffee import CoverPointDef
from toffee import CoverageDatabase
from toffee import CrossDef
from bpuverify.bpu.model.sc.model import TABLES


def coverage():
    axes = dict(bank=(0, 1), common_valid=(0, 1), table=TABLES, feedback=(0, 1), outcome=('wrote', 'blocked'))
    points = tuple(CoverPointDef(key, {str(value): Bin.values(value) for value in values})
                   for key, values in axes.items())
    return CoverGroupDef('sc_common_history_training_gate', points,
        crosses=(CrossDef('bank_history_table_feedback', ('bank', 'common_valid', 'table', 'feedback'), max_auto_bins=8*len(TABLES)),)
        ).instantiate('kunminghu_v3.bpu.sc_common_history_training_gate')


def save(group, output):
    write_functional_coverage(CoverageDatabase((group,)), output_path(output / 'functional-coverage-common-history-training-gate.json'))
