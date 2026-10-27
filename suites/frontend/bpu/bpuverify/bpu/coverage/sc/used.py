"""Independent full-domain SC-used coverage definitions; fresh counts per case."""
from toffee import Bin, CoverGroupDef, CoverPointDef, CrossDef

KINDS = ('used_correct_agree', 'used_correct_disagree', 'used_wrong')


def used_coverage():
    axes = dict(bank=(0, 1), way=(0, 1, 2, 3), kind=KINDS)
    points = tuple(CoverPointDef(axis,
        {str(value): Bin.values(value) for value in values}, weight=0)
        for axis, values in axes.items())
    return CoverGroupDef('sc_used_feedback_gates', points,
        crosses=(CrossDef('physical_used_feedback', tuple(axes), max_auto_bins=24),)
    ).instantiate('kunminghu_v3.bpu.sc_used_feedback_gates')


def history_coverage():
    axes = dict(bank=(0, 1), way=(0, 1, 2, 3),
        direction=('forward', 'backward'), kind=KINDS)
    points = tuple(CoverPointDef(axis,
        {str(value): Bin.values(value) for value in values}, weight=0)
        for axis, values in axes.items())
    return CoverGroupDef('sc_used_nonzero_common_history', points,
        crosses=(CrossDef('physical_used_nonzero_history', tuple(axes), max_auto_bins=48),)
    ).instantiate('kunminghu_v3.bpu.sc_used_nonzero_common_history')
