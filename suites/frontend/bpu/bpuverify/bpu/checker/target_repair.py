"""Full-target comparison with a narrow, antecedent-safe known-defect result."""
from toffee import CheckContext, Scoreboard, ScoreboardMode

from bpuverify.bpu.transaction.types import BpuStage1Source


class MissingMicroFullTargetRepair(AssertionError):
    """Only an established MicroBTB wrap with no causal repair qualifies."""


def check_micro_target_repair(transaction, repairs, *, pc, target, position):
    """Main's independent positive control is required by the calling scenario.

    `repairs` contains the entire causal window, not a target-filtered search.
    Invalid preparation, wrong/extra repairs and association errors are ordinary
    comparison failures; only the absent repair has the known-defect type.
    Address units are the integrated halfword API, with 22 local target bits.
    """
    board = Scoreboard('bpu.micro-full-target-repair')
    context = CheckContext(board.name, ScoreboardMode.DIRECT,
        request=dict(pc=pc, target=target, position=position,
                     prediction_tick=transaction.prediction_tick,
                     metadata_tick=transaction.meta_tick))
    early, perf = transaction.prediction, transaction.meta.perf
    board.check(expected=(pc, position, 1, 0, 0),
        actual=(early.start_pc, early.position, early.taken, early.s2_override, early.s3_override),
        context=context)
    board.check(expected=(pc, early.target, 1, position, BpuStage1Source.UBTB),
        actual=(perf.start_pc, perf.s1_target, perf.s1_taken, perf.s1_position, perf.s1_source),
        context=context)
    wrapped = (pc // (1 << 22)) * (1 << 22) + target % (1 << 22)
    board.check(expected=True, actual=early.target in (target, wrapped), context=context)
    board.check(expected=True,
        actual=transaction.prediction_tick < transaction.meta_tick, context=context)

    if early.target == target:
        # An upstream full-target fix also satisfies the requirement, without
        # authorizing spurious extra corrections to the same target.
        board.check(expected=(), actual=tuple(repairs), context=context)
        return
    if not repairs:
        raise MissingMicroFullTargetRepair(
            f'MicroBTB wrap has no full-target repair: pc={pc:#x}, '
            f'early={early.target:#x}, expected={target:#x}, '
            f'causal_window=({transaction.prediction_tick}, {transaction.meta_tick}]')
    board.check(expected=1, actual=len(repairs), context=context)
    tick, correction = repairs[0]
    board.check(expected=True,
        actual=transaction.prediction_tick < tick <= transaction.meta_tick, context=context)
    board.check(expected=(pc, target, 1, position),
        actual=(correction.start_pc, correction.target, correction.taken, correction.position),
        context=context)
    board.check(expected=True,
        actual=(correction.s2_override, correction.s3_override) in ((1, 0), (0, 1)),
        context=context)
