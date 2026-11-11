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


def guarded_halfword(vaddr):
    """Project a 50-bit prefetch.i byte address as ``PcInit(vaddr).signGuard``."""
    start = vaddr >> 1
    if start & (1 << 48):
        start |= 1 << 49
    return start


def queued_geometry(start):
    """The queued (non-FDIP) request only defines start/set0/source."""
    index = start // 32 % 256
    return Geometry(start, 0, index, 0, False, 0, 0)


@dataclass(frozen=True, slots=True)
class QueuedPrefetch:
    uid: tuple
    start: int
    source: int = 1

    def geometry(self):
        return queued_geometry(self.start)


class PrefetchStore:
    """DefaultConfig FTQ software-prefetch queue (8 slots, one reserved).

    ``enq`` accepts valid lanes in program order while ``numAvailable`` space
    remains; excess lanes and excess ports are silently dropped because Ftq
    deliberately does not back-pressure the load units.  Dequeue happens only
    when the selected ICache prefetch request fires.  Enqueue uses the
    pre-edge occupancy, so a simultaneous dequeue cannot admit a new entry
    into a full queue in the same cycle.
    """

    SIZE = 8
    RESERVED = 1

    def __init__(self):
        self.slots = [None] * self.SIZE
        self.enq = self.deq = 0

    def reset(self):
        self.slots = [None] * self.SIZE
        self.enq = self.deq = 0

    @property
    def distance(self):
        return self.enq - self.deq

    def head(self, index=0):
        if index >= self.distance:
            return None
        return self.slots[(self.deq + index) % self.SIZE]

    def enqueue(self, rows, *, epoch, slot):
        available = self.SIZE - self.RESERVED - self.distance
        accepted = dropped = 0
        for lane, item in enumerate(rows):
            if item is None:
                continue
            if accepted >= available:
                dropped += 1
                continue
            index = (self.enq + accepted) % self.SIZE
            assert self.slots[index] is None, 'prefetch queue overwrote a live entry'
            self.slots[index] = QueuedPrefetch(
                (epoch, slot, 'soft-prefetch', lane), guarded_halfword(item.vaddr))
            accepted += 1
        self.enq += accepted
        return accepted, dropped

    def dequeue(self, count):
        assert 0 <= count <= self.distance, 'prefetch queue dequeued more than it holds'
        for index in range(count):
            self.slots[(self.deq + index) % self.SIZE] = None
        self.deq += count

    def receipt(self):
        return dict(distance=self.distance,
                    entries=tuple(self.slots[(self.deq + index) % self.SIZE].uid
                                  for index in range(self.distance)))


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
