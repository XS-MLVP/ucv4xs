"""Observe actual short/long write occurrences, including unexpected writes."""
from toffee import Bundle
from suites.frontend.bpu.ports.bindings import PortBinding
from suites.frontend.bpu.monitors.cycle import CycleMonitor
from suites.frontend.bpu.utage.bundle.values import _plain
from suites.frontend.bpu.utage.monitor.selective_protection import Monitor as LearningMonitor


class Monitor(LearningMonitor):
    def __init__(self, agent):
        super().__init__(agent)
        self.cursors = CycleMonitor(PortBinding(agent.dut.clock,
            Bundle(cursors=tuple(shadow.binding.bits.enq for shadow in self.shadows)),
            'utage.dual-source-write-cursors'), decoder=_plain)
        self.last_cursors = (0,0)
        self.native_updates = []

    def start(self):
        initial = tuple(self.cursors.sample_at(self.agent.reference.last_event).value['cursors'])
        if initial != (0,0): raise AssertionError('normal reset must clear both actual write cursors')
        return super().start()

    def capture(self, event):
        super().capture(event)
        if self.failure is not None: return
        try:
            current = tuple(self.cursors.sample_at(event).value['cursors'])
            changed = tuple(table for table,(old,new) in enumerate(zip(self.last_cursors,current,strict=True)) if old != new)
            if changed:
                if any((current[t]-self.last_cursors[t])%8 != 1 for t in changed):
                    raise AssertionError('one actual retained version per table per boundary required')
                self.native_updates.append(dict(tick=event.tick, tables=changed,
                    before=self.last_cursors, after=current,
                    cells={str(table):self.shadows[table].sample_at(event).value['cells'][(current[table]-1)%8]
                        for table in changed}))
            self.last_cursors = current
            if self.records and self.records[-1]['tick'] == event.tick:
                self.records[-1]['native_cursors'] = current
        except Exception as error:
            self.failure = error
