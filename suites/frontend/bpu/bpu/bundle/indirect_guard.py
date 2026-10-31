"""Static read-only view of indirect learning, service and region state."""
from toffee import Bundle
from suites.frontend.bpu.bpu.bundle.indirect_service import indirect_service_binding
from suites.frontend.bpu.bpu.bundle.ittage_region import region_binding
from suites.frontend.bpu.ports.bindings import PortBinding


def indirect_guard_binding(agent):
    directory = region_binding(agent).bits
    services = tuple(indirect_service_binding(agent, table=t, bank=b)[0].bits
        for t in range(3) for b in range(2))
    bits = Bundle(reset=agent.dut.reset, region_write=directory.ports.write_valid,
        regions=directory.state, updates=tuple(t.valid for t in directory.target_updates),
        incoming=tuple(s.incoming.valid for s in services), maintenance=tuple(s.maintenance for s in services),
        write_valid=tuple(s.write.valid for s in services), write_ready=tuple(s.write.ready for s in services),
        reads=tuple(s.read.valid for s in services))
    return PortBinding(agent.dut.clock, bits, 'bpu.unexecuted-indirect-learning')
