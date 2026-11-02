"""DefaultConfig request geometry from byte intervals, never live pin values."""
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Geometry:
    start: int
    next_line: int
    set0: int
    set1: int
    cross_line: bool
    bank0: int
    bank1: int


def geometry(start, end_position):
    byte_start = 2 * start
    byte_end = byte_start // 32 * 32 + 2 * end_position
    cross = byte_start // 64 != byte_end // 64
    low, high = (byte_start % 64) // 8, (byte_end % 64) // 8
    first = sum(1 << bank for bank in range(8) if bank >= low and (cross or bank <= high))
    second = sum(1 << bank for bank in range(8) if cross and bank <= high)
    index = byte_start // 64 % 256
    return Geometry(start, (start + 32) % (1 << 50), index, (index + 1) % 256, cross, first, second)


def prefetch_case(first, second, *, eligible):
    if not eligible or first.start // 2048 != second.start // 2048:
        return 0
    return (int(first.set0 == second.set0)
        + 2 * int(first.cross_line and not second.cross_line and first.set1 == second.set0)
        + 4 * int(second.cross_line and not first.cross_line and second.set1 == first.set0)
        + 8 * int(not first.cross_line and not second.cross_line and bool((first.set0 ^ second.set0) & 1)))


def distance_bits(left, right):
    """Transport-only distance for backwards/out-of-order port pressure.

    Legal queue distances are ordinary nonnegative ages. CircularQueuePtr's
    same-flag subtraction is six bits *before* the seven-bit mux extension;
    treating every invalid backwards distance as modulo128 invents a new ABI.
    """
    return ((left % 64 - right % 64) % 64 if left // 64 == right // 64
            else (64 + left % 64 - right % 64) % 128)


def fetch_size(start, end_position):
    # Producer windows have positive extent. Retain the existing full port
    # domain as six-bit unsigned characterization, not a negative byte range.
    return (end_position + 1 - start % 16) % 64
