"""Reject cross-instruction counter chains and missing independent learning."""
from toffee import Scoreboard
from suites.frontend.bpu.utage.checker.dual_source import Checks as VectorChecks
from suites.frontend.bpu.utage.checker.query_cohort import Checks as FeedbackChecks


class Checks(VectorChecks):
    def __init__(self,program):
        super().__init__(program)
        self.board=Scoreboard('utage.complete-instruction-confidence')

    @staticmethod
    def expected_vector(positions,state):
        result=VectorChecks.expected_vector(positions,state)
        return tuple(None if value is None else dict(value,base=int(value['position'] in (2,7))) for value in result)

    def consume(self,label,step,handle,source,monitor):
        positions=self.program.positions(consumer=True)
        token=self.query(label,positions,step.after,handle,source,monitor)
        self.check(True,handle.accepted_event.tick>monitor.records[step.ordinal]['tick'],
            'fresh complete vector follows the actual checked learning boundary')
        self.consumers.append(dict(label=label,after=step.ordinal,original=token,
            accepted=handle.accepted_event.tick,expected=self.expected_vector(positions,step.after),
            actual=self.actual_vector(source,positions)))

    def finish(self,monitor):
        self.check(len(self.program.steps),self.compared,'every learning boundary is checked, not only final confidence')
        self.check(len(self.program.steps),len(monitor.native_updates),'all actual complete native write occurrences are retained')
        FeedbackChecks.finish(self,monitor)
        ticks=[r['tick'] for r in monitor.public[-3:]]
        delta=ticks[2]-ticks[1]
        self.check(True,delta==2 if self.program.mode=='adjacent' else delta>2,'actual original feedback cadence')
        effect=monitor.records[8]['tick']
        first=ticks[1]
        self.check(True,ticks[0]<ticks[1]<effect if self.program.mode=='adjacent' else ticks[1]>effect,
            'late original really overlaps installation or follows its completed effect')
        for step in self.program.steps[-2:]:
            query=self.queries[self.sent[step.ordinal]]
            self.check(True,query['completed']<ticks[0],'old original is fully captured before installation starts')
        count=9 if self.program.mode=='adjacent' else 12
        self.check(count,len(self.consumers),'all mandatory setup and post-learning consumers are present')
        return dict(installation_offered=ticks[0],installation_effect=effect,
            first_old_offered=first,second_old_offered=ticks[2],late_delta=delta)
