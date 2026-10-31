"""Read-only bounded failure context; observations never initialize golden."""
from toffee import Bundle
from suites.frontend.bpu.ports.bindings import PortBinding
from suites.frontend.bpu.runtime.memory_direct import memory_signal,memory_signal_names
from suites.frontend.bpu.bpu.bundle.feedback_gate import full_input_binding


def binding(agent,**options):
    base=full_input_binding(agent,**options)
    anchor,=[n for n in memory_signal_names(agent.dut) if n.endswith('.mbtb.io_enable')]
    prefix=anchor.removeprefix('TOP.').removesuffix('io_enable')
    signal=lambda name:memory_signal(agent.dut,prefix+'alignBanks_0.'+name)
    def bank(index):
        stem=f'internalBanks_{index}.io_read_'
        return Bundle(valid=signal(stem+'req_valid'),row=signal(stem+'req_bits_setIdx'),
            entries=tuple(Bundle(tag=signal(stem+f'resp_entries_{way}_tag'),
                position=signal(stem+f'resp_entries_{way}_position'),
                kind=signal(stem+f'resp_entries_{way}_attribute_branchType'),
                counter=signal(stem+f'resp_counters_{way}_value')) for way in range(2)))
    diagnostic=Bundle(pc1=signal('s1_startPc_addr'),pc2=signal('s2_startPc_addr'),
        mask1=signal('s1_internalBankMask'),hits2=tuple(signal(f's2_rawHitMask_{way}') for way in range(2)),
        predictions2=tuple(Bundle(valid=signal(f's2_predictions_{way}_valid'),
            taken=signal(f's2_predictions_{way}_bits_taken')) for way in range(2)),
        late=Bundle(enabled=memory_signal(agent.dut,prefix.removesuffix('mbtb.')+'tage.io_enable'),
            fast_valid=memory_signal(agent.dut,prefix.removesuffix('mbtb.')+'tage.io_prediction_fastTakenVec_1_valid'),
            fast_taken=memory_signal(agent.dut,prefix.removesuffix('mbtb.')+'tage.io_prediction_fastTakenVec_1_bits'),
            final_valid=memory_signal(agent.dut,prefix.removesuffix('mbtb.')+'tage.io_prediction_takenVec_1_valid')),
        banks=tuple(bank(index) for index in range(2)))
    return PortBinding(base.clock,Bundle(inputs=base.bits.inputs,observed=base.bits.observed,
        complete_metadata=base.bits.complete_metadata,complete_training=base.bits.complete_training,
        read_diagnostic=diagnostic),'bpu.bounded-original-input-and-read-context')
