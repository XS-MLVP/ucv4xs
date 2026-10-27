"""bpuverify.ras.monitor.observation components."""
from bpuverify.common.model.configuration import *


from bpuverify.common.env.memory_direct import memory_signal
from bpuverify.common.env.memory_direct import memory_signal_names
from toffee import Bundle
from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.common.monitor.cycle import CycleMonitor
from bpuverify.ras.bundle.values import _plain


def committed_state(dut):
    """Read-only actual retained groups; never reference-model inputs."""
    names = tuple(memory_signal_names(dut))

    def signal(field):
        suffix = '.Ras.RasStack.' + field
        matches = [name for name in names if name.endswith(suffix)]
        if len(matches) != 1:
            raise RuntimeError(f'RAS state signal {suffix} needs one memory-direct binding; got {matches}')
        return memory_signal(dut, matches[0].split('.', 1)[1])

    return Bundle(head=signal('nsp'), cells=tuple(Bundle(address=signal(f'commitStack_{slot}_retAddr_addr'),
        counter=signal(f'commitStack_{slot}_ctr')) for slot in range(RAS_GROUPS)))


class RasCommittedMonitor(CycleMonitor):
    def __init__(self, agent):
        dut = agent.dut
        names = tuple(memory_signal_names(dut))

        def signal(field):
            suffix = '.Ras.RasStack.' + field
            matches = [name for name in names if name.endswith(suffix)]
            if len(matches) != 1:
                raise RuntimeError(f'RAS state signal {suffix} needs one memory-direct binding; got {matches}')
            return memory_signal(dut, matches[0].split('.', 1)[1])

        cells = tuple(Bundle(address=signal(f'commitStack_{slot}_retAddr_addr'),
            counter=signal(f'commitStack_{slot}_ctr')) for slot in range(RAS_GROUPS))
        binding = PortBinding(dut.clock, Bundle(reset=dut.reset, enable=agent.ports.speculative.bits.enable,
            speculative=Bundle(valid=agent.ports.speculative.valid, bits=agent.ports.speculative.bits),
            commit=Bundle(valid=agent.ports.commit.valid, bits=agent.ports.commit.bits),
            redirect=Bundle(valid=agent.ports.redirect.valid, bits=agent.ports.redirect.bits),
            public=agent.ports.state.bits, head=signal('nsp'), cells=cells,
            bos=Bundle(flag=signal('bos_flag'), value=signal('bos_value')),
            pending_commit=Bundle(valid=signal('io_commit_valid'), push=signal('io_commit_pushValid'),
                pop=signal('io_commit_popValid'), ssp=signal('io_commit_metaSsp'),
                tosw=Bundle(flag=signal('io_commit_metaTosw_flag'), value=signal('io_commit_metaTosw_value')))),
            'ras.committed_observation')
        super().__init__(binding, decoder=_plain)
