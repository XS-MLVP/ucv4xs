"""Static train-response words; shared write/history views stay in their bundle."""
from toffee import Bundle
from bpuverify.bpu.bundle.joint_direction_learning import joint_learning_binding
from bpuverify.bpu.bundle.statistical import TABLES
from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.common.env.memory_direct import memory_signal,memory_signal_names


def joint_originals_binding(agent,**options):
    binding=joint_learning_binding(agent,**options)
    anchor,=[n for n in memory_signal_names(agent.dut) if n.endswith('.sc.io_trainReady')]
    prefix=anchor.removeprefix('TOP.').removesuffix('io_trainReady')
    words=tuple(tuple(memory_signal(agent.dut,prefix+f'{table}.io_trainReadResp_{i}_ctr_value')
        for i in range(16 if table=='biasTable' else 4)) for table in TABLES)
    return PortBinding(binding.clock,Bundle(inputs=binding.bits.inputs,
        observed=Bundle(**dict(binding.bits.observed),joint_SC_train_words=words)),
        'bpu.joint-originals')
