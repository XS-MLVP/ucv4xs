"""StoreDataCtrl comparison with invalid-payload normalization."""
from toffee import CheckContext, Scoreboard, ScoreboardMode


def _normalize(value):
    read_req = value.vrf_read_req if value.vrf_read_req.valid else (False, 0, 0, 0, 0)
    store_data = tuple(value.store_data)
    updates = tuple(
        update if update.valid else (False, 0, 0)
        for update in value.update
    )
    return read_req, store_data, updates


class Checker:
    def __init__(self):
        self.board = Scoreboard('storedata.outputs')
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
