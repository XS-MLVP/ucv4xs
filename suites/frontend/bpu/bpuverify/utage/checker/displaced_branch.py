"""Actual resident instruction and both native write masks, not final value only."""
from toffee import Scoreboard
from bpuverify.utage.checker.dual_source import Checks as VectorChecks
from bpuverify.utage.model.displaced_branch import EARLY


class Checks(VectorChecks):
    def __init__(self, program):
        super().__init__(program)
        self.board = Scoreboard('utage.displaced-original-instruction')

    def consume(self, label, step, transfer, source, monitor):
        positions = self.program.positions(consumer=True)
        token = self.query(label,positions,step.after,transfer,source,monitor)
        effect = monitor.records[step.ordinal]['tick']
        self.check(True,transfer.accepted_event.tick > effect,'new three-instruction consumer follows the actual effect')
        self.consumers.append(dict(label=label,after=step.ordinal,original=token,
            accepted=transfer.accepted_event.tick,expected=self.expected_vector(positions,step.after),
            actual=self.actual_vector(source,positions)))

    def resident(self, monitor):
        step = self.program.steps[self.program.preparation_count-1]
        native = monitor.native_updates[step.ordinal]
        self.check((0,),tuple(native['tables']),'the cold original installs exactly the declared current short owner')
        self.check(step.cell(0),native['cells']['0'],'actual tag, instruction position, confidence and row of the new owner')
        self.check(True,all(self.queries[self.sent[s.ordinal]]['completed'] < monitor.public[step.ordinal]['tick']
            for s in self.program.steps[-2:]),'both late sources are immutable completed occurrences before takeover')
        self.check((EARLY,EARLY),tuple(s.sources[0].position for s in self.program.steps[-2:]),
            'neither late original silently changes to the current instruction position')

    def finish(self, monitor):
        delta = super().finish(monitor)
        self.resident(monitor)
        late = self.program.steps[-2:]
        for step in late:
            source = self.queries[self.sent[step.ordinal]]
            effect = monitor.records[step.ordinal]
            self.check(True,source['completed'] < monitor.native_updates[self.program.preparation_count-1]['tick'] <
                monitor.public[step.ordinal]['tick'] < effect['tick'],
                'late feedback really crosses the observed actual current-owner installation')
        self.check((6,7,7),tuple([late[0].before[1].counter]+[s.after[1].counter for s in late]),
            'a discriminating companion confidence change is mandatory, followed by a real upper hold write')
        return delta
