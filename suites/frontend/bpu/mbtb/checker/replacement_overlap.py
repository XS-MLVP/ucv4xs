"""Same semantic comparison in UT and composition; pytest owns failure verdicts."""
from toffee import CheckContext, Scoreboard, ScoreboardMode

RULES = ('original-source-identity','actual-input-cadence','declared-victim',
         'complete-resident-readback','immutable-original-snapshots')
# XSPComm/Reactor timestamps are half ticks. This is a clock-unit conversion,
# not a DUT latency, settling delay or test scheduling instruction.
HALF_TICKS_PER_CYCLE=2


class ReplacementChecks:
    def __init__(self, program, coverage, scope):
        self.program,self.coverage=program,coverage
        self.board=Scoreboard(scope+'.main-replacement-overlap')
        self.accepted=()
        self.read=set()

    def check(self, expected, actual, point):
        self.board.check(expected=expected,actual=actual,context=CheckContext(self.board.name,
            ScoreboardMode.DIRECT,request=dict(point=point,program=self.program.state(),accepted=self.accepted)))

    def sources(self, actual, expected):
        self.coverage.record('reached','original-source-identity')
        self.check(expected,actual,'two normally obtained, independently qualified original sources')
        self.coverage.record('checked','original-source-identity')

    def admissions(self, ticks, actual, expected):
        self.accepted=tuple(ticks)
        self.coverage.record('reached','actual-input-cadence',tick=ticks[-1] if ticks else None)
        self.check(expected,actual,'complete original-source public feedback and order')
        self.check(1 if self.program.lookup_only else 2,len(ticks),'all actual inputs accepted exactly once')
        if not self.program.lookup_only:
            self.check(HALF_TICKS_PER_CYCLE,ticks[1]-ticks[0],'successive actual feedback clock cycles')
        self.coverage.record('checked','actual-input-cadence',tick=ticks[-1])
        self.coverage.record('reached','declared-victim',tick=ticks[-1])

    def profile(self, pc, actual):
        self.coverage.record('reached','complete-resident-readback')
        expected=tuple((r.way,r.position,r.target,r.counter) for r in self.program.profile(pc))
        self.check(expected,actual,'fresh complete MainBTB identities, counters, targets and ways')
        self.read.add(pc)
        if pc==self.program.new.pc:
            actual_way=next(way for way,position,_,_ in actual if position==self.program.new.position)
            self.check(self.program.victim,actual_way,'latest-age victim, not a sampled-state nomination')
            self.coverage.record('checked','declared-victim')
        if self.read==set(self.program.pcs.values()):
            self.coverage.record('checked','complete-resident-readback')

    def immutable(self, frozen, actual):
        self.coverage.record('reached','immutable-original-snapshots')
        self.check(frozen,actual,'all original source snapshots remain immutable')
        self.coverage.record('checked','immutable-original-snapshots')
        self.check(set(self.program.pcs.values()),self.read,'every surviving and independent context consumed')
