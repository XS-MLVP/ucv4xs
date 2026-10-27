"""Integrated FTQ feedback retirement is distinct from continuous fastTrain.

ABTB/MicroTAGE fastTrain follows S3 predictions, not FTQ feedback. Including
it in an active-stream FTQ drain would wait forever. Read-free operations may
add the write-buffer condition after stopping new prediction reads.
"""
from bpuverify.common.bundle.activity import bind_activity


def training_activity(dut):
    return bind_activity(dut, 'Bpu', {
        'pipeline': (r'tage\.t[0-3]_fire', r'tage\.tables_\d+\.writeReqValid',
                     r'sc\.t[01]_fire', r'sc\.t2_writeValid',
                     r'(?:sc\.(?:pathTable_\d+|globalTable_\d+|bwTable_\d+|imliTable|biasTable))\.updateValid',
                     r'ittage\.updateValid_REG', r'ittage\.tables_\d+_io_update_valid_REG',
                     r'mbtb\.t1_fire',
                     r'mbtb\.alignBanks_\d+\.t0_fire',
                     r'mbtb\.alignBanks_\d+\.internalBanks_\d+\.entryWriteBuffer_io_write_\d+_valid_REG'),
        'writes': (r'tage\.tables_\d+\.tage_entry_write_buffer_bank\d+\.io_read_\d+_valid',
                   r'tage\.tables_\d+\.tage_useful_write_buffer_bank\d+_way\d+\.io_deq_valid',
                   r'tage\.usefulResetInFlight', r'tage\.tables_\d+\.io_usefulResetInFlight',
                   r'ittage\.tables_\d+\.ittage_write_buffer_bank\d+\.io_read_\d+_valid',
                   r'ittage\.tables_\d+\.needReset',
                   r'ittage\.tables_\d+_io_update_resetUsefulCnt_REG',
                   r'sc\.(?:pathTable_\d+|globalTable_\d+|bwTable_\d+|imliTable|biasTable)\.writeBuffer_\d+\.io_read_\d+_valid',
                   r'mbtb\.alignBanks_\d+\.internalBanks_\d+\.entryWriteBuffer\.io_read_\d+_valid',
                   r'mbtb\.alignBanks_\d+\.internalBanks_\d+\.counterWriteBuffer\.io_deq_valid'),
        'reads': (r's[01]_fire',),
        'fast_pipeline': (r's3_valid', r'abtb\.t[12]_fire', r'utage\.t0_fire_REG|utage\.t1_fire'),
        'fast_writes': (r'abtb\.banks_\d+\.writeBuffer\.io_read_\d+_valid',),
    }, name='bpu.training_activity')


def control_activity(dut):
    return bind_activity(dut, 'Bpu', {
        'enable': (r'csrCtrl_delay\.REG_1_(?:ubtb|abtb|mbtb|tage|sc|ittage|ras)Enable',),
    }, name='bpu.applied_control')
