"""MainBTB feedback stages, registered entry writes and counter queues."""
from bpuverify.common.bundle.activity import bind_activity


def training_activity(dut):
    return bind_activity(dut, 'MainBtb', {
        'pipeline': (r't1_fire', r'alignBanks_\d+\.t0_fire',
                     r'alignBanks_\d+\.internalBanks_\d+\.entryWriteBuffer_io_write_\d+_valid_REG'),
        'writes': (r'alignBanks_\d+\.internalBanks_\d+\.entryWriteBuffer\.io_read_\d+_valid',
                   r'alignBanks_\d+\.internalBanks_\d+\.counterWriteBuffer\.io_deq_valid'),
    }, name='mbtb.training_activity')
