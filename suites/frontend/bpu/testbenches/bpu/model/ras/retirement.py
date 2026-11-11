"""Return-address calculation for the integrated BPU retirement contract."""


def return_address(pc, position):
    """Public BPU addresses are halfwords; MiniConfig RAS aligns 16 bytes."""
    if type(pc) is not int or not 0 <= pc < 1 << 50:
        raise ValueError('pc must be an unsigned 50-bit pruned address')
    if type(position) is not int or not 0 <= position < 16:
        raise ValueError('position must be an unsigned four-bit halfword position')
    return ((pc & ~7) + position + 1) & ((1 << 50) - 1)
