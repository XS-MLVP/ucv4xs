"""bpuverify.bpu.case.ras.retirement components."""

from bpuverify.common.env.memory_direct import memory_signal
from bpuverify.common.env.memory_direct import memory_signal_names
from dataclasses import dataclass
from toffee import Bundle
from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.common.bundle.bindings import PulseBinding
from bpuverify.common.bundle.bindings import bind_bundle
from bpuverify.common.bundle.bindings import bind_pulse


def return_address(pc, position):
    """Public BPU addresses are halfwords; MiniConfig RAS aligns 16 bytes."""
    if type(pc) is not int or not 0 <= pc < 1 << 50:
        raise ValueError('pc must be an unsigned 50-bit pruned address')
    if type(position) is not int or not 0 <= position < 16:
        raise ValueError('position must be an unsigned four-bit halfword position')
    return ((pc & ~7) + position + 1) & ((1 << 50) - 1)


@dataclass(frozen=True)
class CommitPorts:
    commit: PulseBinding
    observation: PortBinding

    @classmethod
    def bind(cls, agent):
        dut = agent.dut
        io = bind_bundle(dut, ('io',), name='bpu.retirement.io').bits
        full = bind_pulse(dut, ('io', 'fromFtq', 'commit'), name='bpu.commit')
        commit = PulseBinding(full.clock, full.valid, full.bits.view_as({
            'action': 'attribute.rasAction', 'branch_type': 'attribute.branchType',
            'meta': 'meta_ras'}, path='bpu.commit.bits'), full.name)
        names = tuple(memory_signal_names(dut))
        matches = [name for name in names if name.endswith('.ras.RasStack.nsp')]
        if len(matches) != 1:
            raise RuntimeError(f'unique integrated committed RAS required: {matches!r}')
        stack = matches[0].split('.', 1)[1].removesuffix('nsp')
        ras = stack.removesuffix('RasStack.')

        def signal(prefix, field):
            result = memory_signal(dut, prefix + field)
            if result is None:
                raise RuntimeError(f'RAS memory-direct leaf unavailable: {prefix + field}')
            return result

        state = Bundle(head=signal(stack, 'nsp'), cells=tuple(
            Bundle(address=signal(stack, f'commitStack_{slot}_retAddr_addr'),
                   counter=signal(stack, f'commitStack_{slot}_ctr')) for slot in range(8)))
        pending = Bundle(valid=signal(stack, 'io_commit_valid'),
            push=signal(stack, 'io_commit_pushValid'), pop=signal(stack, 'io_commit_popValid'),
            ssp=signal(stack, 'io_commit_metaSsp'), tosw=Bundle(
                flag=signal(stack, 'io_commit_metaTosw_flag'), value=signal(stack, 'io_commit_metaTosw_value')))
        spec = Bundle(valid=signal(ras, 'io_specIn_valid'), enable=signal(ras, 'io_enable'),
            action=signal(ras, 'io_specIn_bits_attribute_rasAction'),
            pc_bytes=signal(ras, 'io_specIn_bits_startPc'),
            position=signal(ras, 'io_specIn_bits_cfiPosition'))
        observation = PortBinding(dut.clock, Bundle(reset=dut.reset, state=state,
            pending=pending, spec=spec, commit=Bundle(valid=commit.valid, bits=commit.bits),
            public_meta=Bundle(valid=agent.ports.meta.valid,
                pc=agent.ports.meta.bits.perf.start_pc, bits=io.toFtq.meta.bits.commitMeta_ras)),
            'bpu.committed_observation')
        return cls(commit, observation)
