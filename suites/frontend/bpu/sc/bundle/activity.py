"""Sc.scala T0/T1 and each table's update/buffer occupancy."""
from suites.frontend.bpu.ports.activity import bind_activity


def training_activity(dut):
    return bind_activity(dut, 'Sc', {
        'pipeline': (r'io_stageCtrl_t0_fire|t1_fire', r't2_writeValid',
                     r'(?:pathTable_\d+|globalTable_\d+|bwTable_\d+|imliTable|biasTable)\.updateValid'),
        'writes': (r'(?:pathTable_\d+|globalTable_\d+|bwTable_\d+|imliTable|biasTable)\.writeBuffer_\d+\.io_read_\d+_valid',),
    }, name='sc.training_activity')
