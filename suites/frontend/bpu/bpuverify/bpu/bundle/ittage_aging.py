"""Static memory-direct public source, T1, cursor and actual SRAM write view."""
from toffee import Bundle
from bpuverify.common.env.memory_direct import memory_signal,memory_signal_names
from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.bpu.model.ittage_aging import SETS,BANKS


def aging_binding(agent):
    anchor,=[n for n in memory_signal_names(agent.dut) if n.endswith('.ittage.tickCnt_value')]
    prefix=anchor.removeprefix('TOP.').removesuffix('tickCnt_value')
    signal=lambda leaf:memory_signal(agent.dut,prefix+leaf)
    def table(t):
        leaf=lambda name:signal(f'tables_{t}.{name}')
        def bank(b):
            buf=lambda name:leaf(f'ittage_write_buffer_bank{b}.{name}')
            ram=lambda name:leaf(f'ittage_table_bank{b}.{name}')
            return Bundle(enqueue=Bundle(valid=buf('io_write_0_valid'),index=buf('io_write_0_bits_setIdx'),
                mask=buf('io_write_0_bits_bitmask'),useful=buf('io_write_0_bits_entry_usefulCnt_value')),
                ram=Bundle(valid=ram('io_w_req_valid'),ready=ram('io_w_req_ready'),
                    index=ram('io_w_req_bits_setIdx'),mask=ram('io_w_req_bits_bitmask'),
                    useful=ram('io_w_req_bits_data_0_usefulCnt_value')))
        return Bundle(busy=leaf('needReset'),index=leaf('resetSet'),advance=leaf('usefulCanReset'),
            request=Bundle(valid=leaf('io_req_valid'),ready=leaf('io_req_ready')),
            start=leaf('io_update_resetUsefulCnt'),
            update=Bundle(valid=leaf('io_update_valid'),pc=leaf('io_update_startPc_addr'),
                allocate=leaf('io_update_alloc'),old_counter=leaf('io_update_oldCnt_value'),
                correct=leaf('io_update_correct'),useful_valid=leaf('io_update_usefulCntValid'),
                useful=leaf('io_update_usefulCnt_value')),
            banks=tuple(bank(b) for b in range(BANKS)))
    stage=Bundle(valid=signal('updateValid'),pc=signal('t1_train_r_startPcVec_dup_0_0_addr'),
        provider=signal('t1_meta_r_provider_valid'),counter=signal('t1_meta_r_providerCnt_value'),
        target=signal('r_addr'),allocate=signal('t1_meta_r_allocate_valid'),
        branches=tuple(Bundle(valid=signal(f't1_train_r_branches_{i}_valid'),
            target=signal(f't1_train_r_branches_{i}_bits_target_addr'),
            taken=signal(f't1_train_r_branches_{i}_bits_taken'),
            kind=signal(f't1_train_r_branches_{i}_bits_attribute_branchType'),
            mispredict=signal(f't1_train_r_branches_{i}_bits_mispredict')) for i in range(8)))
    return PortBinding(agent.dut.clock,Bundle(reset=agent.dut.reset,enable=signal('io_enable'),
        counter=signal('tickCnt_value'),stage=stage,tables=tuple(table(t) for t in range(len(SETS))),
        feedback_valid=agent.ports.training.valid,feedback_ready=agent.ports.training.ready),'bpu.ittage.aging')
