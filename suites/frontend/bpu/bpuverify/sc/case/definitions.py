from bpuverify.common.model.configuration import *
PC, POSITION, TAGE_COUNTER = 0x4000_0040, 4, 4
TAKEN_ATTEMPTS = 32
NOT_TAKEN_ATTEMPTS = 64
SATURATION_ATTEMPTS = 80
# Zero folded histories and a 0x20 PC stride keep the SRAM bank unchanged
# while selecting four distinct indices, within each write buffer's capacity.
SAME_BANK_PCS = tuple(PC + 0x20 * index for index in range(4))
# These positions hash to eight distinct SC ways. Provider counter profiles
# exercise all {strong/weak} x {not-taken/taken} bias selectors in real meta.
MASKED_POSITIONS = (4, 5, 6, 7, 0, 1, 2, 3)
BIAS_COUNTERS = (0, 7, 3, 4)
MASKED_OUTCOMES = (0, 0, 0, 1, 0, 0, 0, 1)
