"""Public VAGQArbiter environment: drive beats, sample, check, cover."""
from dataclasses import dataclass

from suites.vector.vagq.testbenches.arbiter.checker import Checker
from suites.vector.vagq.testbenches.arbiter.coverage import Coverage
from suites.vector.vagq.testbenches.arbiter.env import probe
from suites.vector.vagq.testbenches.arbiter.model import observe
from suites.vector.vagq.testbenches.arbiter.transactions import Beat


@dataclass
class Env:
    dut: object
    ports: object
    sample: object
    checker: Checker
    coverage: Coverage

    @classmethod
    def create(cls, dut):
        ports, sample = probe.bind(dut)
        return cls(dut, ports, sample, Checker(), Coverage())

    def cycle(self, beat: Beat):
        """Present one combinational beat and compare the routed result."""
        self.ports.inputs.drive(probe.encode(beat))
        actual = self.sample()
        expected = observe(beat)
        self.checker.compare(expected, actual, beat)
        self.coverage.sample(beat, expected)
        return actual

    def assert_clean(self):
        if self.checker.board.status.failed:
            raise AssertionError('VAGQArbiter checker recorded a mismatch')

    def assert_coverage(self, percent=100):
        self.coverage.group.assert_coverage(percent)
