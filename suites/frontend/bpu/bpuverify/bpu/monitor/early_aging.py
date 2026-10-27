"""Bounded memory-direct diagnostics; emit only as a failed-test exception note."""
from collections import deque
import json

from bpuverify.bpu.monitor.bypass.monitor import BypassMonitor


class EarlyAgingDiagnostics:
    def __init__(self, agent):
        self.monitor = BypassMonitor(agent)
        self.rows = deque(maxlen=8)

    def start(self):
        self.monitor.start(self)

    def capture(self, phase, observation):
        tables = []
        for row in observation.value['tables']:
            tables.append(dict(inputs=row['inputs'], response=row['outputs']['response'],
                train_read=row['outputs']['train_read'], write=row['outputs']['write'],
                read_hits=row['state']['hits'], chosen=row['state']['chosen'],
                enq=row['state']['enq'], deq=row['state']['deq'],
                cells=tuple(cell for cell in row['state']['cells'] if cell['valid'])))
        self.rows.append(dict(phase=phase, tick=observation.event.tick, tables=tables))

    def annotate(self, error, lineage):
        error.add_note('Bounded read-only diagnostic context (not a reference input or coverage credit):\n'
                       + json.dumps(dict(actual=list(self.rows), independent=list(lineage)),
                                    default=repr, ensure_ascii=False))

    async def aclose(self):
        await self.monitor.aclose()
