"""Compact association history plus a bounded complete failure window.

Full state is compared live and by independent streaming coverage models.
Historical witnesses keep only fields actually needed by scenario queries.
Fresh monitor snapshots are owned values; projections never mutate them.
"""
from collections import deque
from collections.abc import Sequence


class ObservationHistory(Sequence):
    def __init__(self, project, *, window=8):
        self._project = project
        self._rows = []
        self.by_tick = {}
        self.recent = deque(maxlen=window)

    def append(self, row):
        compact = self._project(row)
        self._rows.append(compact)
        self.by_tick[row['tick']] = compact
        self.recent.append(row)

    def __len__(self):
        return len(self._rows)

    def __getitem__(self, index):
        if isinstance(index, slice):
            return [self[i] for i in range(*index.indices(len(self)))]
        if index < 0:
            index += len(self)
        if not 0 <= index < len(self):
            raise IndexError(index)
        if index == len(self) - 1:
            return self.recent[-1]
        return self._rows[index]


def abtb_witness(row):
    result = {key: value for key, value in row.items() if key != 'state'}
    abtb = {key: value for key, value in row['abtb'].items() if key != 'cells'}
    abtb['replacers'] = tuple({key: value for key, value in bank.items()
        if key not in ('states', 'shadow')} for bank in abtb['replacers'])
    result['abtb'] = abtb
    return result


def bypass_witness(row):
    return dict(row, value={key: value for key, value in row['value'].items()
        if key not in ('tables', 'sram')})


def readback_witness(row):
    value = row['value']
    return dict(row, value=dict(reset=value['reset'], banks=tuple(
        dict(read_input=bank['read_input'], sram=dict(read=bank['sram']['read']))
        for bank in value['banks'])))
