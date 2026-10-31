"""Independent byte-accurate reference for SbufferData.

The model only consumes public transactions (write requests and mask flushes).
It never reads DUT outputs, so it is a valid expectation source for comparisons.
"""
from __future__ import annotations

from dataclasses import dataclass

LINES = 16
LANES = 4
BYTES = 16
LANE_SELECT_MASK = LANES - 1
LINE_MASK = (1 << LINES) - 1
FULL_MASK = (1 << BYTES) - 1


@dataclass(frozen=True)
class WriteRequest:
    """One SbufferData write port transaction (public fields only)."""

    wvec: int
    mask: int
    data: int
    vword_offset: int
    wline: bool = False

    def __post_init__(self) -> None:
        if not 0 <= self.wvec <= LINE_MASK:
            raise ValueError(f"wvec out of range: {self.wvec:#x}")
        if not 0 <= self.mask <= FULL_MASK:
            raise ValueError(f"mask out of range: {self.mask:#x}")
        if not 0 <= self.data < (1 << 128):
            raise ValueError("data must be 128-bit")
        if self.vword_offset < 0:
            raise ValueError("vword_offset must be non-negative")

    @property
    def lane(self) -> int:
        return self.vword_offset & LANE_SELECT_MASK


class SbufferDataModel:
    """16 rows x 4 lanes x 16 bytes of data plus a byte mask and known bits."""

    def __init__(self) -> None:
        self.mask = [[0] * LANES for _ in range(LINES)]
        self.data = [[[0] * BYTES for _ in range(LANES)] for _ in range(LINES)]
        self.known = [[0] * LANES for _ in range(LINES)]

    def reset(self) -> None:
        # reset clears masks; data is not initialized by hardware.
        self.mask = [[0] * LANES for _ in range(LINES)]
        self.known = [[0] * LANES for _ in range(LINES)]

    def flush(self, wvec: int) -> None:
        for line in range(LINES):
            if (wvec >> line) & 1:
                self.mask[line] = [0] * LANES

    def write(self, req: WriteRequest) -> None:
        for line in range(LINES):
            if not (req.wvec >> line) & 1:
                continue
            if req.wline:
                for lane in range(LANES):
                    for byte in range(BYTES):
                        self.data[line][lane][byte] = (req.data >> (8 * byte)) & 0xFF
                    self.mask[line][lane] = FULL_MASK
                    self.known[line][lane] = FULL_MASK
            else:
                lane = req.lane
                for byte in range(BYTES):
                    if (req.mask >> byte) & 1:
                        self.data[line][lane][byte] = (req.data >> (8 * byte)) & 0xFF
                        self.mask[line][lane] |= 1 << byte
                        self.known[line][lane] |= 1 << byte

    def apply(self, writes: tuple[WriteRequest, ...], flush: int | None) -> None:
        # Hardware order: line mask clean first, then port 0, then port 1.
        if flush is not None:
            self.flush(flush)
        for req in writes:
            self.write(req)

    def mask_snapshot(self) -> tuple[int, ...]:
        return tuple(self.mask[line][lane] for line in range(LINES) for lane in range(LANES))

    def known_bytes(self):
        for line in range(LINES):
            for lane in range(LANES):
                known = self.known[line][lane]
                if known:
                    yield line, lane, known, self.data[line][lane]
