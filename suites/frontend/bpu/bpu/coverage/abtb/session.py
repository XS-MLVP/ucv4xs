"""Independent streaming coverage validators for one integrated scenario."""
from suites.frontend.bpu.bpu.coverage.abtb.supplemental import CounterCoverage
from suites.frontend.bpu.bpu.coverage.bypass.supplemental import IntegratedCoverage
from contextlib import nullcontext


class CounterCaseCoverage:
    def __init__(self):
        self.counter, self.bypass = CounterCoverage(), IntegratedCoverage()
        self.counter_replay, self.bypass_replay = self.counter.stream(), self.bypass.stream()
        self.timing = None
        self._validated = False

    def observe_abtb(self, phase, tick, row):
        with self.timing.phase('coverage.counter_validate') if self.timing else nullcontext():
            self.counter_replay.observe(dict(row, phase=phase, tick=tick))

    def observe_bypass(self, phase, tick, row):
        with self.timing.phase('coverage.bypass_validate') if self.timing else nullcontext():
            self.bypass_replay.observe(dict(phase=phase, tick=tick, value=row))

    def validate(self, trace):
        passed = trace.get('passed') is True and not trace.get('failure')
        bypass = self.bypass_replay.validate(passed=passed)
        counter = self.counter_replay.validate(passed=passed)
        self._validated = True
        return bypass, counter

    def commit(self):
        if not self._validated:
            raise RuntimeError('both independent validators must succeed before commit')
        self.bypass_replay.commit()
        self.counter_replay.commit()
        self._validated = False

    def abort(self):
        self._validated = False
        self.bypass_replay.abort()
        self.counter_replay.abort()
