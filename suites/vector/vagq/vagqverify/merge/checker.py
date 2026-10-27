"""MergeCtrl comparison with invalid public output normalization."""
from toffee import CheckContext, Scoreboard, ScoreboardMode


def _normalize(value):
    def state_update(update):
        return update if update.valid else (False, 0, 0)

    return (
        value.updates,
        state_update(value.split_done),
        state_update(value.merge_done),
        state_update(value.rob_clear),
        value.vrf_read if value.vrf_read.valid else (False, 0, 0, 0, 0),
        value.vrf_write if value.vrf_write.valid else (False, 0, 0, 0, 0),
        value.rob_writeback if value.rob_writeback.valid else (False,),
        (value.vp_wakeup_valid, value.vp_wakeup if value.vp_wakeup_valid else 0),
    )


class Checker:
    def __init__(self):
        self.board = Scoreboard('merge.outputs')
        self.cycles = 0

    def compare(self, expected, actual, *, phase, beat):
        self.board.check(
            expected=_normalize(expected),
            actual=_normalize(actual),
            context=CheckContext(
                self.board.name,
                ScoreboardMode.DIRECT,
                sequence_id=self.cycles,
                request={'phase': phase, 'beat': beat},
            ),
        )

    def complete(self):
        self.cycles += 1
