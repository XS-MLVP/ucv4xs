"""MicroBTB's public unguarded byte-address domain, not a signal encoding."""

BYTE_ADDRESS_BITS = 50  # 49 stored halfword bits plus the pruned byte bit0.


def byte_address(value, name):
    if type(value) is not int or not 0 <= value < (1 << BYTE_ADDRESS_BITS) or value & 1:
        raise ValueError(f'MicroBTB {name} must be an unsigned {BYTE_ADDRESS_BITS}-bit, '
                         'halfword-aligned byte address')
    return value
