"""Static memory-direct selector and real training operand view."""
from bpuverify.common.model.configuration import *

from toffee import Bundle
from bpuverify.common.env.memory_direct import memory_signal,memory_signal_names
from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.common.monitor.cycle import CycleMonitor
from bpuverify.bpu.bundle.values import _plain


class TageSelectorMonitor(CycleMonitor):
    def __init__(self,agent):
        anchor,=[name for name in memory_signal_names(agent.dut) if name.endswith('.tage.useAltOnNaVec_0_value')]
        prefix=anchor.removeprefix('TOP.').removesuffix('useAltOnNaVec_0_value')
        signal=lambda leaf:memory_signal(agent.dut,prefix+leaf)
        reads=tuple(tuple(Bundle(valid=signal(f't2_readResp_{table}_entries_{way}_valid'),
            tag=signal(f't2_readResp_{table}_entries_{way}_tag'),
            counter=signal(f't2_readResp_{table}_entries_{way}_takenCtr_value'),
            useful=signal(f't2_readResp_{table}_usefulCtrs_{way}_value'))
            for way in range(2)) for table in range(TAGE_TABLES))
        votes=tuple(Bundle(valid=signal(f't3_trainInfoVec_{slot}_valid'),
            index=signal(f't3_trainInfoVec_{slot}_useAltOnNaIdx'),
            inc=signal(f't3_trainInfoVec_{slot}_incUseAltOnNa'),
            dec=signal(f't3_trainInfoVec_{slot}_decUseAltOnNa')) for slot in range(8))
        parent=lambda leaf:memory_signal(agent.dut,prefix.removesuffix('tage.')+leaf)
        predictions=Bundle(fire=parent('s2_valid'),pc=parent('s2_startPc_dup_2_addr'),
            slots=tuple(Bundle(valid=signal(f'io_prediction_takenVec_{slot}_valid'),
                taken=signal(f'io_prediction_takenVec_{slot}_bits'),
                meta=Bundle(**{key:signal(f'io_meta_entries_{slot}_{key}') for key in (
                    'hasProvider','providerTableIdx','providerWayIdx','providerTakenCtr_value',
                    'hasAlt','altConf','altOrBasePred','useProvider')})) for slot in range(RESULT_SLOTS)))
        training=agent.ports.training
        bits=Bundle(reset=agent.dut.reset,selectors=tuple(signal(f'useAltOnNaVec_{i}_value') for i in range(8)),
            enable=signal('io_enable'),fire=tuple(signal(f't{i}_fire') for i in range(4)),
            use_meta=signal('t2_useMeta'),reads=reads,raw_tags=tuple(signal(f't2_rawTag_{i}') for i in range(TAGE_TABLES)),
            votes=votes,prediction=predictions,training=Bundle(valid=training.valid,ready=training.ready,bits=training.bits))
        super().__init__(PortBinding(agent.dut.clock,bits,'bpu.tage.selector_events'),decoder=_plain)
