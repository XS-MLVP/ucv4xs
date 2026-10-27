"""Port-level environment for CounterFilter.

Cycle contract (calibrated): load ports are captured at a rising edge; queries
are combinational on the committed entry set. An entry enqueued at edge t is
visible for queries in cycles t, t+1, t+2, t+3 (age 0..3) and is dequeued at
edge t+4 by the 4-stage allocation-count pipeline.

Reset calibration: the three pipeline registers `last3CycleAlloc_REG{,_1,_2}` in
CounterFilter.sv have no reset (only `last3CycleAlloc` itself is cleared), so a
short reset leaves their pre-reset values in place; the first post-reset cycle
then dequeues that stale count and advances `deqPtr` past `enqPtr`, permanently
shifting the FIFO. The env therefore holds reset for five idle edges before
releasing it, so the unresettable pipeline is flushed to zero while the pointers
are still held at zero. The RTL fact is recorded as
`CF-DEQUEUE-PIPELINE-NO-RESET` in manifest/known-issues.json; it is benign in
the system because reset is held for many cycles before any load can reach the
filter.
"""
from __future__ import annotations

from .coverage import CounterFilterCoverage
from .model import CounterFilterModel, SIZE
from .coverage import MAX_INFLIGHT


class CounterFilterEnv:
    def __init__(self, dut, coverage: CounterFilterCoverage | None = None) -> None:
        self.dut = dut
        self.coverage = coverage
        self.model = CounterFilterModel()
        self.ld_valid = [getattr(dut, f"io_ld_in_{port}_valid") for port in range(3)]
        self.ld_idx = [getattr(dut, f"io_ld_in_{port}_bits_idx") for port in range(3)]
        self.ld_way = [getattr(dut, f"io_ld_in_{port}_bits_way") for port in range(3)]
        self.q_valid = [getattr(dut, f"io_query_{port}_req_valid") for port in range(3)]
        self.q_idx = [getattr(dut, f"io_query_{port}_req_bits_idx") for port in range(3)]
        self.q_way = [getattr(dut, f"io_query_{port}_req_bits_way") for port in range(3)]
        self.q_resp = [getattr(dut, f"io_query_{port}_resp") for port in range(3)]
        self.cycles = 0
        self.hits = 0
        self.recent_hits: set[tuple[int, int]] = set()

    def _val(self, signal) -> int:
        return int(signal.value)

    def edge(self) -> None:
        self.dut.Step(1)

    def set_cycle(self, loads, queries) -> None:
        """Drive one cycle without advancing the clock."""
        for port in range(3):
            load = loads[port] if port < len(loads) else None
            if load is None:
                self.ld_valid[port].Set(0)
            else:
                idx, way = load
                self.ld_valid[port].Set(1)
                self.ld_idx[port].Set(idx)
                self.ld_way[port].Set(way)
        for port in range(3):
            query = queries[port] if port < len(queries) else None
            if query is None:
                self.q_valid[port].Set(0)
            else:
                idx, way, valid = query
                self.q_valid[port].Set(1 if valid else 0)
                self.q_idx[port].Set(idx)
                self.q_way[port].Set(way)
        self.dut.xclock.RefreshComb()

    def check_queries(self, context: str = "cycle"):
        hits = []
        for port in range(3):
            idx = self._val(self.q_idx[port])
            way = self._val(self.q_way[port])
            valid = bool(self._val(self.q_valid[port]))
            got = bool(self._val(self.q_resp[port]))
            want = self.model.query(idx, way, valid)
            if got != want:
                raise AssertionError(
                    f"{context}: query port {port} (idx={idx}, way={way}, valid={valid}) "
                    f"{got} != {want}; occupancy={self.model.occupancy}")
            age = self.model.matching_age(idx, way) if want else None
            expired = False
            if want:
                self.hits += 1
                self.recent_hits.add((idx, way))
            elif valid and (idx, way) in self.recent_hits:
                expired = True
                self.recent_hits.discard((idx, way))
            if self.coverage is not None:
                result = "invalid" if not valid else ("hit" if want else "miss")
                self.coverage.sample_query(port, result, idx, way,
                                           self.model.occupancy, age, expired)
            hits.append(got)
        return hits

    def step(self, loads, queries, *, context: str = "cycle") -> list[bool]:
        """Drive, sample combinational queries, then commit the clock edge."""
        self.set_cycle(loads, queries)
        hits = self.check_queries(context)
        load_list = [load for load in loads if load is not None]
        event = self.model.step(load_list)
        counts = len(load_list)
        relation = "none"
        if counts:
            relation = "same_line" if len(set(load_list)) < counts else "distinct"
        if self.coverage is not None:
            self.coverage.sample_enq(counts, relation, self.model.occupancy,
                                     event["wrapped"],
                                     event["occupancy"] >= MAX_INFLIGHT)
        self.cycles += 1
        self.edge()
        return hits

    def reset(self) -> None:
        for port in range(3):
            self.ld_valid[port].Set(0)
            self.q_valid[port].Set(0)
        self.dut.reset.Set(1)
        # Five idle edges flush the un-resettable dequeue pipeline while the
        # pointers are still clamped by reset; a shorter reset leaves stale
        # dequeue counts that shift the FIFO permanently.
        for _ in range(5):
            self.edge()
        self.dut.reset.Set(0)
        self.edge()
        self.model = CounterFilterModel()
        self.recent_hits.clear()
        self.cycles = 0
