"""Semantic recovery programs; no ports, DUT values or physical history cells."""
from dataclasses import dataclass

from bpuverify.bpu.model.common_history import Block, Value
from bpuverify.bpu.model.selection import Branch, Kind

PC = 0x40000800
FORWARD, BACKWARD, BRIDGE = PC + 0x200, PC - 0x200, PC + 0x100
POSITIONS = (1, 5)


@dataclass(frozen=True, slots=True)
class RecoveryProfile:
    name: str
    loop: str
    correction: Branch
    original: Value
    restored: Value

    @property
    def first_target(self):
        return BRIDGE if self.loop == 'forward' else PC

    @property
    def first_taken(self):
        return self.loop != 'alternating'

    @property
    def loop_choice(self):
        return Branch(1 if self.first_taken else 5, self.first_target if self.first_taken else PC,
                      Kind.CONDITIONAL, True)

    @property
    def consumer(self):
        return Value(True, self.restored.ghr, self.restored.bw)

    def recover(self, before=None):
        value = self.original if before is None else before
        return value.append(Block(PC, POSITIONS).outcomes(self.correction, recovering=True), valid=False)


PROFILES = (
    RecoveryProfile('forward-conditional', 'backward', Branch(1, FORWARD, Kind.CONDITIONAL, True),
                    Value(True, 65535, 255), Value(False, 65535, 254)),
    RecoveryProfile('backward-conditional', 'forward', Branch(1, BACKWARD, Kind.CONDITIONAL, True),
                    Value(True, 65535, 0), Value(False, 65535, 1)),
    RecoveryProfile('direct-without-prefix', 'backward', Branch(1, FORWARD, Kind.DIRECT, True),
                    Value(True, 65535, 255), Value(False, 65535, 255)),
    RecoveryProfile('direct-after-prefix', 'alternating', Branch(5, FORWARD, Kind.DIRECT, True),
                    Value(True, 21845, 85), Value(False, 43690, 170)),
)
