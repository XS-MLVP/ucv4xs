"""Small explicit environment composing driver, model, checker and coverage."""
from dataclasses import dataclass

from .checker import Checker
from .coverage import Coverage
from .driver import Driver
from .model import IntegrationModel
from .probe import bind
from .types import AddrPacket, Beat, DataPacket


@dataclass
class Env:
    dut: object
    ports: object
    sample: object
    driver: Driver
    model: IntegrationModel
    checker: Checker
    coverage: Coverage

    @classmethod
    def create(cls, dut):
        ports, sample = bind(dut)
        return cls(dut, ports, sample, Driver(dut, ports),
                   IntegrationModel(), Checker(), Coverage())

    def reset(self):
        self.driver.reset_dut()
        self.model = IntegrationModel()
        self.coverage.reset()

    def admit(self, addr: AddrPacket, data: DataPacket):
        self.model.admit(addr, data)

    def cycle(self, beat: Beat, *, admit=None):
        self.driver.drive(beat)
        outputs = self.sample()
        if admit is not None:
            if isinstance(admit, list):
                for addr, data in admit:
                    self.admit(addr, data)
            else:
                self.admit(*admit)
        self.checker.compare(self.model, outputs, beat)
        self.coverage.sample(beat, outputs, self.model)
        self.driver.tick()
        return outputs

    def finish(self):
        self.checker.finish()
