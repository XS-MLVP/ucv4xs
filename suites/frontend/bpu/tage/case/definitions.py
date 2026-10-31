
from suites.frontend.bpu.models.configuration import TAGE_TABLES
PC, POSITION = 0x4000_0000, 6
PC_ALIAS = PC + 0x80
SATURATION_ATTEMPTS = 10
HIGHEST_TABLE = TAGE_TABLES - 1
TAGGED_TABLES = TAGE_TABLES
WAYS_PER_TABLE = 2
USEFUL_SET_POSITIONS = tuple(range(TAGGED_TABLES * WAYS_PER_TABLE))
PRESSURE_POSITION = len(USEFUL_SET_POSITIONS)
USEFUL_RESET_COUNTER_MAX = (1 << 8) - 1
# Zero folded history: PC[8:2] selects distinct rows, PC[1:0] keeps one bank.
SAME_BANK_PCS = tuple(PC + 0x20 * index for index in range(4))
