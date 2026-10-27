"""AheadBtb.scala fast training stages and SRAM write buffers."""
from bpuverify.common.bundle.activity import bind_activity


def training_activity(dut):
    return bind_activity(dut, 'AheadBtb', {
        'pipeline': (r't[12]_fire', r'banks_\d+\.io_writeReq_valid'),
        'writes': (r'banks_\d+\.writeBuffer\.io_read_\d+_valid',),
    }, name='abtb.training_activity')
