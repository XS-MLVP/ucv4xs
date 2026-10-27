"""Integration checker: public payloads are checked only when valid."""
from toffee import CheckContext, Scoreboard, ScoreboardMode

from .model import IntegrationModel


class Checker:
    def __init__(self):
        self.board = Scoreboard('vagq.integration')
        self.sequence = 0

    def compare(self, model: IntegrationModel, outputs, beat):
        try:
            active, empty = model.validate(outputs, beat)
            actual = ('valid', tuple((event['byte_offset'], event['elem_idx'])
                                     for event in active), tuple(empty))
            expected = ('valid', tuple((event['byte_offset'], event['elem_idx'])
                                       for event in active), tuple(empty))
        except AssertionError as error:
            expected = ('contract-valid',)
            actual = ('contract-error', str(error))
        self.board.check(
            expected=expected,
            actual=actual,
            context=CheckContext(
                self.board.name,
                ScoreboardMode.DIRECT,
                sequence_id=self.sequence,
                request=beat,
            ),
        )
        self.sequence += 1

    def finish(self):
        if self.board.status.failed:
            raise AssertionError('VAGQ integration checker recorded a mismatch')
