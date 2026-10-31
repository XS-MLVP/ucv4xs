"""Static TAGE write-port views alongside the existing seven-source sampler."""
from suites.frontend.bpu.models.configuration import *

from toffee import Bundle
from suites.frontend.bpu.bpu.bundle.pipeline import pipeline_binding
from suites.frontend.bpu.ports.bindings import PortBinding
from suites.frontend.bpu.runtime.memory_direct import memory_signal,memory_signal_names
from suites.frontend.bpu.bpu.bundle.tage_semantic import HISTORY_PORTS


def joint_learning_binding(agent,**options):
    binding=pipeline_binding(agent,**options)
    anchor,=[n for n in memory_signal_names(agent.dut) if n.endswith('.tage.io_enable')]
    prefix=anchor.removeprefix('TOP.').removesuffix('tage.io_enable')
    signal=lambda field:memory_signal(agent.dut,prefix+field)
    def table(t):
        base=f'tage.tables_{t}.io_writeReq_'
        return Bundle(valid=signal(base+'valid'),index=signal(base+'bits_setIdx'),bank=signal(base+'bits_bankMask'),
            ways=signal(base+'bits_wayMask'),
            entry_mask=tuple(signal(base+f'bits_writeEntryEn_{w}') for w in range(2)),
            useful_mask=tuple(signal(base+f'bits_writeUsefulEn_{w}') for w in range(2)),
            taken=tuple(signal(base+f'bits_actualTakenMask_{w}') for w in range(2)),
            entries=tuple(Bundle(valid=signal(base+f'bits_entries_{w}_valid'),tag=signal(base+f'bits_entries_{w}_tag'),
                counter=signal(base+f'bits_entries_{w}_takenCtr_value')) for w in range(2)),
            useful=tuple(signal(base+f'bits_usefulCtrs_{w}_value') for w in range(2)))
    return PortBinding(binding.clock,Bundle(inputs=binding.bits.inputs,
        observed=Bundle(**dict(binding.bits.observed),joint_tage=tuple(table(t) for t in range(TAGE_TABLES)),
            joint_train_folds=tuple(signal(f'tage.io_fromPhr_foldedPathHistForTrain_hist_{i}_foldedHist') for i in HISTORY_PORTS))),
        'bpu.joint-direction-learning')
