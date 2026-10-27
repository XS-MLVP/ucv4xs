"""Ittage.scala update-valid register and per-table entry buffers."""
from bpuverify.common.bundle.activity import bind_activity


def training_activity(dut):
    return bind_activity(dut, 'Ittage', {
        'pipeline': (r'updateValid_REG', r'tables_\d+_io_update_valid_REG'),
        'writes': (r'tables_\d+\.ittage_write_buffer_bank\d+\.io_read_\d+_valid',),
    }, name='ittage.training_activity')
