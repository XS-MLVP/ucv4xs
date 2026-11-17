"""BM-04 effective PPN calculation, lifted from the level-merge scenarios."""


def merge_ppn(ppn: int, vpn: int, mask: int) -> int:
    return (ppn & ~mask) | (vpn & mask)
