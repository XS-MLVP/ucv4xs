"""Minimal address-semantic discriminators; no bank/set or raw-pin stimulus."""
from dataclasses import dataclass

from suites.frontend.bpu.ubtb.transaction.types import BranchTraining, UbtbPrediction
from suites.frontend.bpu.ubtb.coverage.address import AddressCoverage


@dataclass(frozen=True, slots=True)
class AddressCase:
    name: str
    pc: int
    target: int
    expected_target: int
    neighbor_delta: int = 0


CASES = (
    AddressCase('instruction-byte-bit1', 0x80001000, 0x80002340, 0x80002340, 2),
    AddressCase('distinct-tag-byte-bit22', 0x80001000, 0x80002340, 0x80002340, 1 << 22),
    AddressCase('stored-target-byte-bit22', 0x80001000, 0x80402340, 0x80402340),
    AddressCase('eight-mib-forward-wrap', 0x807FFFE0, 0x80800100, 0x80000100),
    AddressCase('eight-mib-backward-wrap', 0x80800000, 0x807FFF00, 0x80FFFF00),
    AddressCase('highest-unguarded-byte-region', (1 << 50) - 0x1000, (1 << 50) - 2, (1 << 50) - 2),
)


async def check_address_case(agent, case):
    coverage = AddressCoverage()
    try:
        await agent.reset()
        await agent.train(BranchTraining(case.pc, case.target, 1, 3, 2))
        first = UbtbPrediction(1, 1, case.expected_target, 3, 2)
        observed = await agent.predict(case.pc)
        if not case.neighbor_delta:
            coverage.record('reached', case.name)
        assert observed == first, case
        if case.neighbor_delta:
            # These PCs have distinct real partial tags. The old binding
            # aliases the 4-MiB pair despite the model's distinct identities.
            neighbor = case.pc + case.neighbor_delta
            observed = await agent.predict(neighbor)
            coverage.record('reached', case.name)
            assert observed.valid == 0, case
            other = BranchTraining(neighbor, 0x80003450, 1, 9, 3)
            await agent.train(other)
            assert await agent.predict(neighbor) == UbtbPrediction(1, 1, other.target, 9, 3), case
            assert await agent.predict(case.pc) == first, case
        coverage.record('checked', case.name)
    finally:
        coverage.write()
