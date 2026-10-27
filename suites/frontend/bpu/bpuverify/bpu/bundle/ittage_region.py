"""Static memory-direct region directory and registered target-update views."""
from toffee import Bundle
from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.common.env.memory_direct import memory_signal, memory_signal_names


def region_binding(agent):
    matches = [n for n in memory_signal_names(agent.dut) if n.endswith('.ittage.rTable.io_writeValid')]
    if len(matches) != 1:
        raise RuntimeError(f'unique ITTAGE region directory required: {matches}')
    prefix = matches[0].removeprefix('TOP.').removesuffix('rTable.io_writeValid')
    signal = lambda name: memory_signal(agent.dut, prefix + name)
    ports = Bundle(write_valid=signal('rTable.io_writeValid'), write_region=signal('rTable.io_writeRegion'),
        write_pointer=signal('rTable.io_writePointer'),
        requests=tuple(signal(f'rTable.io_reqPointer_{i}') for i in range(3)),
        responses=tuple(Bundle(hit=signal(f'rTable.io_respHit_{i}'),
            region=signal(f'rTable.io_respRegion_{i}')) for i in range(3)),
        updates=tuple(Bundle(region=signal(f'rTable.io_updateRegion_{i}'),
            hit=signal(f'rTable.io_updateHit_{i}'), pointer=signal(f'rTable.io_updatePointer_{i}')) for i in range(2)))
    state = tuple(Bundle(valid=signal(f'rTable.regions_{i}_valid'),
        region=signal(f'rTable.regions_{i}_region')) for i in range(16))
    targets = tuple(Bundle(valid=signal(f'tables_{i}.io_update_valid'),
        pc=signal(f'tables_{i}.io_update_startPc_addr'), allocate=signal(f'tables_{i}.io_update_alloc'),
        old_counter=signal(f'tables_{i}.io_update_oldCnt_value'),
        use_pc_region=signal(f'tables_{i}.io_update_targetOffset_usePcRegion'),
        pointer=signal(f'tables_{i}.io_update_targetOffset_pointer'),
        offset=signal(f'tables_{i}.io_update_targetOffset_offset_addr')) for i in range(3))
    return PortBinding(agent.dut.clock, Bundle(reset=agent.dut.reset, ports=ports, state=state,
        target_updates=targets, feedback_valid=agent.ports.training.valid,
        feedback_ready=agent.ports.training.ready), 'bpu.ittage_region_directory')
