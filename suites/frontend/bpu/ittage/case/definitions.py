
from suites.frontend.bpu.models.configuration import ITTAGE_ROWS
PC, POSITION = 0x4000_0000, 7
TARGET_A, TARGET_B = 0x4000_1234, 0x4000_5678
MAX_UPDATE_ATTEMPTS = 8
HIGHEST_TABLE = len(ITTAGE_ROWS) - 1
REGION_COUNT, REGION_WIDTH = 16, 20
# These are byte addresses. Agent encoding prunes bit zero; zero-history
# index bits PC[8:2] then select distinct sets in the same bank.
SAME_BANK_PCS = tuple(PC + 0x20 * index for index in range(4))
PENDING_TARGETS = tuple(0x4002_1000 + 0x20 * index for index in range(4))
