"""Toffee environment for SbufferData: drive public ports, compare a byte model.

Timing contract used here (verified against the generated RTL):
a request driven in the stable phase is captured at the next rising edge and
becomes visible at the following rising edge. The helper therefore checks
"no early visibility" at the capture edge and "exact match" at the commit edge.
"""
from __future__ import annotations

from dataclasses import dataclass

from toffee import RisingEdge

from .coverage import SbufferDataCoverage
from .model import BYTES, LANES, LINES, SbufferDataModel, WriteRequest


@dataclass(frozen=True)
class Op:
    """One cycle of public stimulus.

    ``ports`` selects which write ports carry ``writes`` (default: 0, 1, ...).
    """

    writes: tuple[WriteRequest, ...] = ()
    flush: int | None = None
    ports: tuple[int, ...] | None = None

    def active(self):
        ports = self.ports if self.ports is not None else tuple(range(len(self.writes)))
        if len(ports) != len(self.writes):
            raise ValueError("ports and writes length differ")
        return list(zip(ports, self.writes, strict=True))


class SbufferDataEnv:
    def __init__(self, dut, coverage: SbufferDataCoverage | None = None) -> None:
        self.dut = dut
        self.coverage = coverage
        self.model = SbufferDataModel()
        self.mask_sigs = [
            [
                [getattr(dut, f"io_maskOut_{line}_{lane}_{byte}") for byte in range(BYTES)]
                for lane in range(LANES)
            ]
            for line in range(LINES)
        ]
        self.data_sigs = [
            [
                [getattr(dut, f"io_dataOut_{line}_{lane}_{byte}") for byte in range(BYTES)]
                for lane in range(LANES)
            ]
            for line in range(LINES)
        ]
        self.write_pins = [
            {
                "valid": getattr(dut, f"io_writeReq_{port}_valid"),
                "wvec": getattr(dut, f"io_writeReq_{port}_bits_wvec"),
                "mask": getattr(dut, f"io_writeReq_{port}_bits_mask"),
                "data": getattr(dut, f"io_writeReq_{port}_bits_data"),
                "vword": getattr(dut, f"io_writeReq_{port}_bits_vwordOffset"),
                "wline": getattr(dut, f"io_writeReq_{port}_bits_wline"),
            }
            for port in range(2)
        ]
        self.flush_pins = {
            "valid": getattr(dut, "io_maskFlushReq_0_valid"),
            "wvec": getattr(dut, "io_maskFlushReq_0_bits_wvec"),
        }
        self.transactions = 0
        self.checked_edges = 0

    # ------------------------------------------------------------------ clock
    async def _edge(self) -> None:
        await RisingEdge(self.dut.clock)

    # ------------------------------------------------------------------ reads
    def read_masks(self, lines=None) -> dict[int, tuple[int, ...]]:
        selected = range(LINES) if lines is None else lines
        result = {}
        for line in selected:
            values = []
            for lane in range(LANES):
                value = 0
                for byte, signal in enumerate(self.mask_sigs[line][lane]):
                    if int(signal.value):
                        value |= 1 << byte
                values.append(value)
            result[line] = tuple(values)
        return result

    # ------------------------------------------------------------------ check
    def check(self, context: str, lines=None) -> None:
        selected = list(range(LINES) if lines is None else lines)
        actual = self.read_masks(selected)
        for line in selected:
            for lane in range(LANES):
                got = actual[line][lane]
                want = self.model.mask[line][lane]
                if got != want:
                    raise AssertionError(
                        f"{context}: mask mismatch line={line} lane={lane} "
                        f"expected={want:#06x} actual={got:#06x}"
                    )
        for line in selected:
            for lane in range(LANES):
                known = self.model.known[line][lane]
                if not known:
                    continue
                expected_data = self.model.data[line][lane]
                for byte, signal in enumerate(self.data_sigs[line][lane]):
                    if not (known >> byte) & 1:
                        continue
                    want = expected_data[byte]
                    got = int(signal.value) & 0xFF
                    if got != want:
                        raise AssertionError(
                            f"{context}: data mismatch line={line} lane={lane} byte={byte} "
                            f"expected={want:#04x} actual={got:#04x}"
                        )
        self.checked_edges += 1

    # ------------------------------------------------------------------ drive
    def _drive_op(self, op: Op) -> None:
        for port in range(2):
            self.write_pins[port]["valid"].Set(0)
        for port, req in op.active():
            pins = self.write_pins[port]
            pins["valid"].Set(1)
            pins["wvec"].Set(req.wvec)
            pins["mask"].Set(req.mask)
            pins["data"].Set(req.data)
            pins["vword"].Set(req.vword_offset)
            pins["wline"].Set(1 if req.wline else 0)
        if op.flush is None:
            self.flush_pins["valid"].Set(0)
        else:
            self.flush_pins["wvec"].Set(op.flush)
            self.flush_pins["valid"].Set(1)

    def _clear_pins(self) -> None:
        for pins in self.write_pins:
            pins["valid"].Set(0)
        self.flush_pins["valid"].Set(0)

    def _commit(self, op: Op, context: str, lines=None) -> None:
        self.model.apply(op.writes, op.flush)
        self.check(context, lines)
        self.transactions += 1
        if self.coverage is not None:
            self.coverage.sample_op(op.writes, op.flush)

    # ------------------------------------------------------------------ cases
    async def reset(self, context: str = "reset_idle") -> None:
        self.dut.reset.Set(1)
        await self._edge()
        await self._edge()
        self.model.reset()
        self.dut.reset.Set(0)
        await self._edge()
        self.check("after reset")
        if self.coverage is not None:
            self.coverage.sample_reset(context)

    async def idle(self, cycles: int = 3, context: str = "after_write") -> None:
        for index in range(cycles):
            await self._edge()
            self.check(f"idle cycle {index}")
        if self.coverage is not None:
            self.coverage.sample_idle(context)

    async def burst(self, ops: tuple[Op, ...] | list[Op], lines_per_op=None) -> None:
        if not ops:
            raise ValueError("burst requires at least one op")
        if lines_per_op is not None and len(lines_per_op) != len(ops):
            raise ValueError("lines_per_op length differs from ops")
        self._drive_op(ops[0])
        for index, op in enumerate(ops):
            await self._edge()  # capture of op[index]; commit of op[index - 1]
            if index == 0:
                self.check("capture latency")
            else:
                lines = None if lines_per_op is None else lines_per_op[index - 1]
                self._commit(ops[index - 1], f"burst op {index - 1}", lines)
            if index + 1 < len(ops):
                self._drive_op(ops[index + 1])
            else:
                self._clear_pins()
        await self._edge()
        lines = None if lines_per_op is None else lines_per_op[-1]
        self._commit(ops[-1], f"burst op {len(ops) - 1}", lines)
        if lines_per_op is not None:
            self.check("burst end full check")

    async def issue(self, writes: tuple[WriteRequest, ...] = (), flush: int | None = None) -> None:
        await self.burst([Op(tuple(writes), flush)])

    async def invalid_write(self, req: WriteRequest) -> None:
        self._drive_op(Op((req,), None))
        self.write_pins[0]["valid"].Set(0)  # payload present, valid low
        await self._edge()
        self.check("invalid write capture")
        await self._edge()
        self.check("invalid write commit")
        self._clear_pins()

    async def invalid_flush(self, wvec: int) -> None:
        self.flush_pins["wvec"].Set(wvec)
        self.flush_pins["valid"].Set(0)
        await self._edge()
        await self._edge()
        self.check("invalid flush")
        self._clear_pins()

    async def reset_pending_write(self, req: WriteRequest) -> None:
        self._drive_op(Op((req,), None))
        await self._edge()  # capture in s1
        self.check("pending write capture")
        self.dut.reset.Set(1)
        self._clear_pins()
        await self._edge()  # s2 would commit here, reset cancels it
        self.model.reset()
        await self._edge()
        self.dut.reset.Set(0)
        await self._edge()
        self.check("after reset cancels pending write")
        if self.coverage is not None:
            self.coverage.sample_reset("reset_pending_write")

    async def reset_with_flush(self, wvec: int) -> None:
        self.flush_pins["wvec"].Set(wvec)
        self.flush_pins["valid"].Set(1)
        self.dut.reset.Set(1)
        await self._edge()
        await self._edge()
        self.model.reset()
        self.dut.reset.Set(0)
        self._clear_pins()
        await self._edge()
        self.check("after reset with flush")
        if self.coverage is not None:
            self.coverage.sample_reset("reset_with_flush")
