"""Direct comparison and durable ownership checks, independent of scheduling."""
from dataclasses import fields
from toffee import CheckContext, Scoreboard, ScoreboardMode


class PersistenceChecks:
    def __init__(self, program, ledger):
        self.program, self.ledger = program, ledger
        self.board = Scoreboard('utage.learning-persistence')

    def check(self, wanted, actual, point, *, phases):
        self.board.check(expected=wanted, actual=actual, context=CheckContext(self.board.name,
            ScoreboardMode.DIRECT, request=dict(point=point, program=self.program.state(),
                phases=phases, accepted=len(self.ledger.feedback), published=len(self.ledger.published),
                services=len(self.ledger.services))))

    def persistent(self, owners, actual_memory, *, phases):
        versions = tuple(self.ledger.sources[owner][0] for owner in owners)
        expected = {version.identity[:2]: version.entry for version in versions}
        actual = {key: actual_memory[key] for key in expected if key in actual_memory}
        # Show the native expected/actual mismatch in pytest before reporting
        # missing service receipts. Both independent conditions remain required.
        self.check(expected, actual, 'latest accepted learning persists in actual SRAM', phases=phases)
        self.ledger.finish_phase(owners, persistent=True)

    def status_snapshot(self):
        """Export public counters and text, never deepcopy an exception."""
        status = self.board.status
        result = {field.name: getattr(status, field.name) for field in fields(status)
                  if field.name != 'first_failure'}
        result['mode'] = status.mode.value
        result['first_failure'] = None if status.first_failure is None else str(status.first_failure)
        return result
