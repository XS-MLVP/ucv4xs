"""Tage.scala T0..T3 -> registered table request -> entry/useful buffers."""
from bpuverify.common.bundle.activity import bind_activity


def training_activity(dut):
    return bind_activity(dut, 'Tage', {
        'pipeline': (r'io_stageCtrl_t0_fire|t[1-3]_fire', r'tables_\d+\.writeReqValid'),
        'writes': (r'tables_\d+\.tage_entry_write_buffer_bank\d+\.io_read_\d+_valid',
                   r'tables_\d+\.tage_useful_write_buffer_bank\d+_way\d+\.io_deq_valid'),
        'reads': (r'io_stageCtrl_s0_fire',),
    }, name='tage.training_activity')
