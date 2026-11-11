"""Address helpers shared by the LoadPipe checks."""

VADDR_BITS = 50
PADDR_BITS = 48
BLOCK_OFF = 6


def dcache_index(vaddr: int) -> int:
    hi = 0
    for bit in range(12, 48, 2):
        hi ^= (vaddr >> bit) & 0x3
    low = (vaddr >> 6) & 0x3F
    return ((hi & 0x3) << 6) | low


def block(paddr: int) -> int:
    return (paddr >> BLOCK_OFF) & ((1 << (PADDR_BITS - BLOCK_OFF)) - 1)


def mask_class(mask: int, load128: bool) -> str:
    if load128:
        return "load128"
    if mask == 0:
        return "zero"
    if mask == 0xFFFF:
        return "full"
    bits = mask.bit_count()
    if bits == 1:
        return "single_byte"
    low = (mask & -mask).bit_length() - 1
    shifted = mask >> low
    if shifted & (shifted + 1) == 0:
        return "byte_range"
    return "scattered"
