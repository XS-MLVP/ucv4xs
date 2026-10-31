"""Deterministic MicroTAGE vectors."""

PASSING_PC = 0x4000_0000
DEFECT_PC = 0x4000_0800
POSITION = 5
SATURATION_ATTEMPTS = 8
# Legacy MicroTAGE API uses encoded PrunedAddr.addr, not byte addresses.
# These two PCs plus low-four-bit history profiles provide eight independent
# indices per bank without changing the known GuardedPc tag-width defect.
SHADOW_PCS = (PASSING_PC, PASSING_PC + 0x40)
SHADOW_CAPACITY = 8
SHADOW_REPEAT_BEATS = 12
