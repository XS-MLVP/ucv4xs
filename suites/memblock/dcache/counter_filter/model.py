"""Independent FIFO model for CounterFilter (15 entries, 3 enq, 3 query)."""
from __future__ import annotations

SIZE = 15
PORTS = 3
MAX_ALLOC = 3


class CounterFilterModel:
    def __init__(self) -> None:
        self.entries = [(0, 0)] * SIZE
        self.valids = [False] * SIZE
        self.age = [0] * SIZE
        self.enq_val = 0
        self.enq_flag = 0
        self.deq_val = 0
        self.deq_flag = 0
        self.r1 = 0
        self.r2 = 0
        self.r3 = 0
        self.last3 = 0
        self.occupancy = 0
        self.enq_wrapped = False
        self.alloc_ports = 0
        self.same_line_duplicate = False
        self.full_alloc = False

    # ---------------------------------------------------------------- query
    def query(self, idx: int, way: int, valid: bool) -> bool:
        if not valid:
            return False
        return any(valid_flag and entry == (idx, way)
                   for valid_flag, entry in zip(self.valids, self.entries))

    def matching_age(self, idx: int, way: int) -> int | None:
        for slot, (valid_flag, entry) in enumerate(zip(self.valids, self.entries)):
            if valid_flag and entry == (idx, way):
                return self.age[slot]
        return None

    # ---------------------------------------------------------------- cycle
    def _position(self, offset: int) -> tuple[int, int]:
        total = self.enq_val + offset
        return total % SIZE, self.enq_flag ^ (1 if total >= SIZE else 0)

    def _can_alloc(self, offset: int) -> bool:
        pos, flag = self._position(offset)
        return bool(flag ^ self.deq_flag ^ (1 if pos >= self.deq_val else 0))

    def step(self, loads: list[tuple[int, int]] | tuple[tuple[int, int], ...]) -> dict:
        """Commit one clock edge with the given load ports (None entries absent)."""
        valid_ports = [load for load in loads]
        positions = []
        allocs = []
        for index, load in enumerate(valid_ports):
            pos, _flag = self._position(len(allocs))
            if not self._can_alloc(len(allocs)):
                raise AssertionError(
                    f"counter filter overflow: port {index} cannot allocate at "
                    f"enq={self.enq_val} deq={self.deq_val} last3={self.last3}")
            positions.append(pos)
            allocs.append(load)
        self.enq_wrapped = self.enq_val + len(allocs) >= SIZE
        self.alloc_ports = len(allocs)
        self.same_line_duplicate = len(allocs) > 1 and len(set(allocs)) < len(allocs)
        self.full_alloc = (self.occupancy + len(allocs)) == SIZE

        # Dequeue first, then enqueue (enqueue wins on a shared slot).
        for offset in range(self.last3):
            self.valids[(self.deq_val + offset) % SIZE] = False
        for pos, (idx, way) in zip(positions, allocs):
            self.entries[pos] = (idx, way)
            self.valids[pos] = True
            self.age[pos] = 0
        # Ages advance for all entries that survive this edge.
        for slot in range(SIZE):
            if self.valids[slot] and slot not in positions:
                self.age[slot] += 1
        # Advance pointers.
        total_deq = self.deq_val + self.last3
        self.deq_val = total_deq % SIZE
        self.deq_flag ^= 1 if total_deq >= SIZE else 0
        total_enq = self.enq_val + len(allocs)
        self.enq_val = total_enq % SIZE
        self.enq_flag ^= 1 if total_enq >= SIZE else 0
        # Four-stage allocation-count pipeline.
        self.r1, self.r2, self.r3, self.last3 = (
            len(allocs), self.r1, self.r2, self.r3)
        self.occupancy = sum(1 for flag in self.valids if flag)
        return {"alloc_ports": len(allocs), "occupancy": self.occupancy,
                "wrapped": self.enq_wrapped}
