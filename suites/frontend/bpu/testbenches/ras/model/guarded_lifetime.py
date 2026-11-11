"""Guarded call-return boundary classes; arithmetic is in byte address space."""
CFI_BYTES = (6, (1 << 49) + 6, (1 << 50) + 6, (1 << 50) + (1 << 49) + 6, (1 << 51) - 2)
LIFETIME_KINDS = ('guarded-stack-lifetime',)


def retained_return(pc):
    if type(pc) is not int or pc < 0 or pc >= 1 << 51 or pc % 2:
        raise ValueError('guarded instruction end must be an even 51-bit byte PC')
    return ((pc + 2) % (1 << 51)) // 2
