"""PMP standalone environment: distributed CSR writes and pmp/pma outputs."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from toffee import RisingEdge


class PmpEnv:
    def __init__(self, dut, coverage=None) -> None:
        self.dut = dut
        self.coverage = coverage
        self.tick = 0
        d = dut
        self.dist = dict(valid=d.io_distribute_csr_w_valid,
                         addr=d.io_distribute_csr_w_bits_addr,
                         data=d.io_distribute_csr_w_bits_data)
        self.pmp = []
        self.pma = []
        for index in range(32):
            self.pmp.append({
                "l": getattr(d, f"io_pmp_{index}_cfg_l"),
                "a": getattr(d, f"io_pmp_{index}_cfg_a"),
                "x": getattr(d, f"io_pmp_{index}_cfg_x"),
                "w": getattr(d, f"io_pmp_{index}_cfg_w"),
                "r": getattr(d, f"io_pmp_{index}_cfg_r"),
                "addr": getattr(d, f"io_pmp_{index}_addr"),
                "mask": getattr(d, f"io_pmp_{index}_mask"),
            })
            self.pma.append({
                "c": getattr(d, f"io_pma_{index}_cfg_c"),
                "atomic": getattr(d, f"io_pma_{index}_cfg_atomic"),
                "a": getattr(d, f"io_pma_{index}_cfg_a"),
                "x": getattr(d, f"io_pma_{index}_cfg_x"),
                "w": getattr(d, f"io_pma_{index}_cfg_w"),
                "r": getattr(d, f"io_pma_{index}_cfg_r"),
                "addr": getattr(d, f"io_pma_{index}_addr"),
                "mask": getattr(d, f"io_pma_{index}_mask"),
            })

    async def edge(self) -> None:
        await RisingEdge(self.dut.clock)
        self.tick += 1

    def read(self, signal) -> int:
        return int(signal.value)

    async def reset(self) -> None:
        self.dist["valid"].Set(0)
        self.dist["addr"].Set(0)
        self.dist["data"].Set(0)
        self.dut.reset.Set(1)
        await self.edge()
        await self.edge()
        self.dut.reset.Set(0)
        await self.edge()
        # Generated RTL initializes PMA entries from the SoC PMAConfigs list;
        # capture that documented default table for the reference model.
        reference = Path(__file__).resolve().parents[2] / "manifest/pma-reset-reference.json"
        self.pma_default = json.loads(reference.read_text())["entries"]
        assert self.snapshot("pma") == self.pma_default, "PMA reset differs from fixed configuration oracle"

    async def write(self, addr: int, data: int) -> None:
        self.dist["valid"].Set(1)
        self.dist["addr"].Set(addr & 0xFFF)
        self.dist["data"].Set(data & ((1 << 64) - 1))
        await self.edge()
        self.dist["valid"].Set(0)
        self.dist["data"].Set(0)
        await self.edge()

    def entry(self, table: str, index: int) -> dict:
        return (self.pmp if table == "pmp" else self.pma)[index]

    def read_entry(self, table: str, index: int) -> dict:
        return {key: self.read(sig) for key, sig in self.entry(table, index).items()}

    def snapshot(self, table: str) -> list[dict]:
        return [self.read_entry(table, index) for index in range(32)]


@dataclass
class Cfg:
    l: int = 0
    c: int = 0
    atomic: int = 0
    a: int = 0
    x: int = 0
    w: int = 0
    r: int = 0

    def byte(self) -> int:
        return ((self.l & 1) << 7 | (self.c & 1) << 6 | (self.atomic & 1) << 5
                | (self.a & 3) << 3 | (self.x & 1) << 2 | (self.w & 1) << 1
                | (self.r & 1))

    @classmethod
    def from_byte(cls, value: int) -> "Cfg":
        return cls(l=(value >> 7) & 1, c=(value >> 6) & 1,
                   atomic=(value >> 5) & 1, a=(value >> 3) & 3,
                   x=(value >> 2) & 1, w=(value >> 1) & 1, r=value & 1)

    def coarsened(self) -> "Cfg":
        cfg = Cfg(l=self.l, c=self.c, atomic=self.atomic,
                  a=((self.a >> 1) << 1) | ((self.a >> 1) | (self.a & 1)),
                  x=self.x, w=self.w & self.r, r=self.r)
        return cfg


def match_mask(paddr: int, a_low: int) -> int:
    x = ((paddr & ((1 << 46) - 1)) << 1) | (a_low & 1)
    x |= (4096 - 1) >> 2
    mask = x & ~(x + 1)
    return ((mask << 2) | 3) & ((1 << 48) - 1)


class PmpModel:
    """Reference model of the documented PMP/PMA CSR programming rules."""

    def __init__(self, pma_default: list[dict] | None = None) -> None:
        pma = [dict(c=0, atomic=0, a=0, x=0, w=0, r=0, addr=0, mask=0xFFF)
               for _ in range(32)]
        if pma_default is not None:
            pma = [dict(entry) for entry in pma_default]
        self.entries = {
            "pmp": [dict(l=0, a=0, x=0, w=0, r=0, addr=0, mask=0) for _ in range(32)],
            "pma": pma,
        }

    def write_cfg(self, table: str, base_index: int, data: int) -> None:
        for offset in range(8):
            index = base_index + offset
            if index >= 32:
                break
            entry = self.entries[table][index]
            old_l = entry["l"] if table == "pmp" else 0
            if old_l:
                continue
            raw = Cfg.from_byte((data >> (8 * offset)) & 0xFF)
            cfg = raw.coarsened()
            entry["a"] = cfg.a
            entry["x"] = cfg.x
            entry["w"] = cfg.w
            entry["r"] = cfg.r
            if table == "pmp":
                entry["l"] = cfg.l
            else:
                entry["c"] = cfg.c
                entry["atomic"] = cfg.atomic
            if cfg.a & 2:
                entry["mask"] = match_mask(entry["addr"], cfg.a & 1)

    def write_addr(self, table: str, index: int, data: int) -> None:
        entry = self.entries[table][index]
        next_cfg = (self.entries[table][index + 1]
                    if index + 1 < 32 else dict(l=0, a=0))
        locked = (entry.get("l", 0) == 1
                  or (next_cfg.get("l", 0) == 1 and next_cfg.get("a", 0) == 1))
        if locked:
            return
        entry["addr"] = data & ((1 << 46) - 1)
        entry["mask"] = match_mask(entry["addr"], entry["a"] & 1)

    def snapshot(self, table: str) -> list[dict]:
        return [dict(entry) for entry in self.entries[table]]
