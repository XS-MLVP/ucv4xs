"""Read-only complete MicroBTB owners beside history lifetime observation."""
from toffee import Bundle

from bpuverify.bpu.bundle.ahead_working_set import working_set_binding
from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.common.env.memory_direct import memory_signal, memory_signal_names
from toffee.signals import signal_width


def history_working_set_binding(agent, **options):
    binding = working_set_binding(agent, **options)
    anchor, = [name for name in memory_signal_names(agent.dut) if name.endswith('.ubtb.io_enable')]
    prefix = anchor.removeprefix('TOP.').removesuffix('io_enable')
    fields = dict(key='tag',confidence='usefulCnt_value',target='slot1_target',position='slot1_position',
                  kind='slot1_attribute_branchType',action='slot1_attribute_rasAction')
    entries = tuple(Bundle(**{name:memory_signal(agent.dut,prefix+f'entries_{slot}_'+field)
        for name,field in fields.items()}) for slot in range(32))
    signal = lambda field:memory_signal(agent.dut,prefix+field)
    fast = Bundle(valid=signal('io_fastTrain_valid'),pc=signal('io_fastTrain_bits_startPc_addr'),
        **{name:signal('io_fastTrain_bits_branch_'+field) for name,field in dict(target='target_addr',
            taken='taken',position='cfiPosition',kind='attribute_branchType',action='attribute_rasAction').items()})
    resolve = Bundle(fire=signal('io_stageCtrl_t0_fire'),pc=signal('io_train_startPcVec_dup_0_0_addr'),
        valid=signal('io_train_branches_0_valid'),
        **{name:signal('io_train_branches_0_bits_'+field) for name,field in dict(target='target_addr',
            taken='taken',position='cfiPosition',kind='attribute_branchType',action='attribute_rasAction',
            mispredict='mispredict').items()})
    return PortBinding(binding.clock,Bundle(inputs=binding.bits.inputs,
        observed=Bundle(**dict(binding.bits.observed),micro_entries=entries,micro_fast=fast,micro_resolve=resolve)),
        'bpu.history-working-set')


def short_path_retention_binding(agent,program,**options):
    return short_storage_binding(agent,program.positives,**options)


def short_storage_binding(agent,paths,**options):
    """Actual cache residency and selected native SRAM words, read only."""
    from bpuverify.utage.monitor.shadow import UtageShadowMonitor
    binding=history_working_set_binding(agent,**options)
    prefix,tag_bits,shadow=UtageShadowMonitor._bind(agent,0)
    root=prefix.removesuffix('wbuffer.')
    words=tuple(memory_signal(agent.dut,
        root+f'utage_entry_sram_bank{path.read_indices[0]%4}.array.array_ext.Memory',path.read_indices[0]//4)
        for path in paths)
    position_bits=signal_width(shadow.bits.cells[0].position)
    counter_bits=signal_width(shadow.bits.cells[0].counter)
    padding=signal_width(words[0])-(1+tag_bits+position_bits+counter_bits)
    if padding!=1:raise AssertionError('native short-table entry packing changed')
    actual=Bundle(cells=shadow.bits.cells,words=words)
    return PortBinding(binding.clock,Bundle(inputs=binding.bits.inputs,
        observed=Bundle(**dict(binding.bits.observed),short_storage=actual)),
        'bpu.short-path-retention'),(tag_bits,position_bits,counter_bits,padding)
