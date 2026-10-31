"""Independent transaction-level reference for the Sbuffer top level.

The model tracks store-buffer lines by physical tag, their merged bytes and
their write-out lifecycle. It never predicts the PLRU slot choice: the DUT's
request id is accepted only after its payload is matched against a unique live
line, which keeps slot allocation an implementation detail while still checking
the architectural store-buffer content.
"""
from __future__ import annotations

from dataclasses import dataclass, field

LINES = 16
LANES = 4
BYTES = 16
LANE_MASK = LANES - 1


@dataclass
class Enq:
    ptag: int
    vtag: int
    lane: int
    mask: int
    data: int
    wline: bool = False

    @property
    def addr(self) -> int:
        return (self.ptag << 6) | (self.lane << 4)

    @property
    def vaddr(self) -> int:
        return (self.vtag << 6) | (self.lane << 4)

    @property
    def line_mask(self) -> int:
        if self.wline:
            return (1 << 64) - 1
        return self.mask << (16 * self.lane)

    def data_bytes(self) -> list[int]:
        return [(self.data >> (8 * byte)) & 0xFF for byte in range(BYTES)]


@dataclass
class Line:
    ptag: int
    vtag: int
    mask: list[int] = field(default_factory=lambda: [0] * LANES)
    data: list[list[int]] = field(default_factory=lambda: [[0] * BYTES for _ in range(LANES)])
    inflight: bool = False
    timeout: bool = False

    def line_mask(self) -> int:
        return sum(self.mask[lane] << (16 * lane) for lane in range(LANES))

    def line_data(self) -> int:
        value = 0
        for lane in range(LANES):
            for byte in range(BYTES):
                value |= self.data[lane][byte] << (8 * (16 * lane + byte))
        return value

    def apply(self, req: Enq, *, update_vtag: bool = False) -> None:
        if update_vtag:
            self.vtag = req.vtag
        lanes = range(LANES) if req.wline else (req.lane,)
        payload = req.data_bytes()
        for lane in lanes:
            for byte in range(BYTES):
                if req.wline or (req.mask >> byte) & 1:
                    self.data[lane][byte] = payload[byte]
                    self.mask[lane] |= 1 << byte


class SbufferModel:
    def __init__(self) -> None:
        self.lines: list[Line] = []
        self.uarch_drain = False

    def reset(self) -> None:
        self.lines.clear()
        self.uarch_drain = False

    # ------------------------------------------------------------------ enqueue
    def active_same_tag(self, ptag: int) -> Line | None:
        for line in self.lines:
            if line.ptag == ptag and not line.inflight:
                return line
        return None

    def enqueue(self, requests: list[Enq]) -> None:
        """Apply accepted port requests in port order.

        Two ports writing the same fresh physical tag target the same new slot;
        the later port wins overlapping bytes and its vtag, without an extra
        allocation.
        """
        created_this_cycle: dict[int, Line] = {}
        for req in requests:
            line = self.active_same_tag(req.ptag)
            if line is not None:
                if line.vtag != req.vtag and not req.wline:
                    self.uarch_drain = True
                line.apply(req)
                continue
            created = created_this_cycle.get(req.ptag)
            if created is not None:
                created.apply(req, update_vtag=True)
                continue
            line = Line(ptag=req.ptag, vtag=req.vtag)
            line.apply(req)
            self.lines.append(line)
            created_this_cycle[req.ptag] = line

    def can_merge(self, ptag: int) -> bool:
        return self.active_same_tag(ptag) is not None

    # ------------------------------------------------------------------ writeout
    def candidate_lines(self) -> list[Line]:
        inflight_tags = {line.ptag for line in self.lines if line.inflight}
        return [
            line for line in self.lines
            if not line.inflight and line.ptag not in inflight_tags
        ]

    def unique_line_for_payload(self, ptag: int, vtag: int, mask: int, data: int) -> Line | None:
        matches = [
            line for line in self.lines
            if line.ptag == ptag and line.vtag == vtag
            and line.line_mask() == mask and line.line_data() == data
        ]
        return matches[0] if len(matches) == 1 else None

    def mark_inflight(self, line: Line) -> None:
        line.inflight = True

    def on_hit(self, line: Line) -> None:
        if line in self.lines:
            self.lines.remove(line)

    def on_replay(self, line: Line) -> None:
        line.timeout = True

    # ------------------------------------------------------------------ forward
    def forward(self, vaddr: int, paddr: int) -> tuple[int, list[int], bool]:
        vtag = vaddr >> 6
        ptag = paddr >> 6
        lane = (paddr >> 4) & LANE_MASK
        vmatch = [line for line in self.lines if line.vtag == vtag]
        active = [line for line in vmatch if not line.inflight]
        inflight = [line for line in vmatch if line.inflight]
        mismatch = any((line.vtag == vtag) != (line.ptag == ptag) for line in self.lines)

        mask = 0
        data = [0] * BYTES
        for line in inflight:
            mask |= line.mask[lane]
            for byte in range(BYTES):
                if (line.mask[lane] >> byte) & 1:
                    data[byte] = line.data[lane][byte]
        for line in active:
            mask |= line.mask[lane]
            for byte in range(BYTES):
                if (line.mask[lane] >> byte) & 1:
                    data[byte] = line.data[lane][byte]
        return mask, data, mismatch
