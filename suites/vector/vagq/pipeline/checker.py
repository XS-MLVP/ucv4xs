"""Independent before/after payload and handshake comparisons."""
from toffee import CheckContext, Scoreboard, ScoreboardMode


class Checker:
    def __init__(self, name):
        self.board = Scoreboard(name)
        self.cycles = 0

    def compare(self, expected, actual, *, phase, beat):
        # The generated pipe has no reset assignment for payload registers.
        # Payload is architecturally meaningful only while out_valid is high;
        # ready/valid is always compared, and valid payloads are compared in
        # full. This does not mask a stale payload behind a valid bit.
        self.board.check(
            expected=(expected.in_ready, expected.out_valid,
                      expected.payload if expected.out_valid else None),
            actual=(actual.in_ready, actual.out_valid,
                    actual.payload if actual.out_valid else None),
            context=CheckContext(
                self.board.name, ScoreboardMode.DIRECT,
                sequence_id=self.cycles,
                request={'phase': phase, 'beat': beat},
            ),
        )

    def complete(self):
        self.cycles += 1
