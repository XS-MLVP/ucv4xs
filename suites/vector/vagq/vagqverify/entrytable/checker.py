"""EntryTable comparison with invalid-entry don't-care normalization."""
from toffee import CheckContext, Scoreboard, ScoreboardMode

from .model import ENTRY_FIELDS

STATE_INDEX = ENTRY_FIELDS.index('state')
OP2_INDEX = ENTRY_FIELDS.index('op2_data')
STATIC_START = ENTRY_FIELDS.index('meta_ftq_flag')
STATIC_END = ENTRY_FIELDS.index('nf') + 1


def _normalize(observation):
    entries, addr_ready, data_ready, older = observation
    valid = [row[0] for row in entries]
    normalized = []
    for row in entries:
        if not row[0]:
            normalized.append((0,))
            continue
        values = list(row)
        # waitSI has not received data yet: op2Data is not an architectural
        # value. waitA has not received address metadata: static fields are
        # intentionally not compared until the address source fires.
        if row[STATE_INDEX] == 2:
            values[OP2_INDEX] = 0
        elif row[STATE_INDEX] == 1:
            values[STATIC_START:STATIC_END] = [0] * (STATIC_END - STATIC_START)
        normalized.append(tuple(values))
    normalized_entries = tuple(normalized)
    normalized_older = tuple(
        tuple(value if valid[i] and valid[j] else False for j, value in enumerate(row))
        for i, row in enumerate(older)
    )
    return normalized_entries, addr_ready, data_ready, normalized_older


class Checker:
    def __init__(self):
        self.board = Scoreboard('entrytable.outputs')
        self.cycles = 0

    def compare(self, expected, actual, *, phase, beat):
        self.board.check(
            expected=_normalize(expected), actual=_normalize(actual),
            context=CheckContext(self.board.name, ScoreboardMode.DIRECT,
                                 sequence_id=self.cycles, request={'phase': phase, 'beat': beat}),
        )

    def complete(self):
        self.cycles += 1
