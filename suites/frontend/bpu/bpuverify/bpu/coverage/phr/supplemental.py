"""Retain all physical pointer bins, including not-yet-qualified odd metadata."""

from bpuverify.common.coverage.exports import write_functional_coverage
from bpuverify.common.env.artifacts import output_path
from toffee import Bin
from toffee import CoverGroupDef
from toffee import CoverPointDef
from toffee import CoverageDatabase
from toffee import CrossDef


def bpu_phr_recovery_coverage_model(mode):
    if mode not in ('flowing', 'backpressured'):
        raise ValueError('unknown recovery cadence')
    axes = dict(flag=(0, 1), pointer=range(52), taken=(0, 1))
    points = tuple(CoverPointDef(name, {str(value): Bin.values(value) for value in values})
        for name, values in axes.items())
    return CoverGroupDef('bpu_phr_recovery', points,
        crosses=(CrossDef('all_dimensions', tuple(axes), max_auto_bins=208),)
        ).instantiate('kunminghu_v3.bpu.phr_recovery.' + mode)


def write_bpu_phr_recovery_coverage(coverage, output, mode):
    write_functional_coverage(CoverageDatabase([coverage]), output_path(output / 'results/bpu' /
        ('functional-coverage-phr-recovery-' + mode + '.json')))


"""Each mid/late repair cadence requires six post-comparison observations."""
from toffee import Bin
from toffee import CoverGroupDef
from toffee import CoverPointDef
from toffee import CoverageDatabase

DIRECTION_PHASES = ('public_correction', 'pointer_restore', 'pending_restore',
    'all_physical_cells', 'all_fold_registers', 'causal_metadata')


def bpu_phr_direction_repair_coverage_model(stage, mode):
    return CoverGroupDef('bpu_phr_direction_repair', (
        CoverPointDef('checked', {name: Bin.values(name) for name in DIRECTION_PHASES}),
    )).instantiate(f'kunminghu_v3.bpu.phr_direction_repair.{stage}.{mode}')


def write_bpu_phr_direction_repair_coverage(coverage, output, stage, mode):
    write_functional_coverage(CoverageDatabase([coverage]), output_path(output / 'results/bpu' /
        f'functional-coverage-phr-direction-repair-{stage}-{mode}.json'))


from toffee import Bin
from toffee import CoverGroupDef
from toffee import CoverPointDef
from toffee import CoverageDatabase

WRAP_PHASES = ('valid_taken_pointer_zero', 'pointer_wrap_and_flag_flip',
    'all_physical_cells', 'all_fold_registers', 'causal_metadata', 'public_correction')


def bpu_phr_taken_wrap_coverage_model(stage, mode):
    return CoverGroupDef('bpu_phr_taken_pointer_wrap', (
        CoverPointDef('checked', {name: Bin.values(name) for name in WRAP_PHASES}),
    )).instantiate(f'kunminghu_v3.bpu.phr_taken_pointer_wrap.{stage}.{mode}')


def write_bpu_phr_taken_wrap_coverage(coverage, output, stage, mode):
    write_functional_coverage(CoverageDatabase([coverage]), output_path(output / 'results/bpu' /
        f'functional-coverage-phr-taken-pointer-wrap-{stage}-{mode}.json'))
