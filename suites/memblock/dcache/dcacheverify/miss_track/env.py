"""Port-level environment for MissTrack.

One model cycle = drive all inputs, compute the expected S1 speculation result
and the next table state, then commit one rising edge and compare the public
`io_spec_*` outputs. An S0 query issued in cycle t is observed in cycle t+1
when its S1 payload is presented.
"""
from __future__ import annotations

from .coverage import MissTrackCoverage
from .model import (
    Alloc,
    Install,
    Invalidate,
    Load,
    MissTrackModel,
    Owner,
    Spec,
    block,
    index,
)


class MissTrackEnv:
    def __init__(self, dut, coverage: MissTrackCoverage | None = None) -> None:
        self.dut = dut
        self.coverage = coverage
        self.model = MissTrackModel()
        self.loads = []
        for lane in range(3):
            self.loads.append({
                "s0_valid": getattr(dut, f"io_loads_{lane}_s0_valid"),
                "s0_vaddr": getattr(dut, f"io_loads_{lane}_s0_vaddr"),
                "s1_valid": getattr(dut, f"io_loads_{lane}_s1_valid"),
                "s1_paddr": getattr(dut, f"io_loads_{lane}_s1_paddr"),
                "s2_valid": getattr(dut, f"io_loads_{lane}_s2_valid"),
                "s2_vaddr": getattr(dut, f"io_loads_{lane}_s2_bits_vaddr"),
                "s2_paddr": getattr(dut, f"io_loads_{lane}_s2_bits_paddr"),
                "s2_way": getattr(dut, f"io_loads_{lane}_s2_bits_way"),
                "s2_hit": getattr(dut, f"io_loads_{lane}_s2_bits_hit"),
            })
        self.allocs = [{
            "valid": getattr(dut, f"io_alloc_{port}_valid"),
            "vaddr": getattr(dut, f"io_alloc_{port}_bits_vaddr"),
            "paddr": getattr(dut, f"io_alloc_{port}_bits_paddr"),
            "mshr_id": getattr(dut, f"io_alloc_{port}_bits_mshr_id"),
        } for port in range(4)]
        self.owners = [{
            "valid": getattr(dut, f"io_owners_{slot}_valid"),
            "vaddr": getattr(dut, f"io_owners_{slot}_bits_vaddr"),
            "paddr": getattr(dut, f"io_owners_{slot}_bits_paddr"),
        } for slot in range(16)]
        self.install = {
            "valid": dut.io_install_valid,
            "vaddr": dut.io_install_bits_vaddr,
            "paddr": dut.io_install_bits_paddr,
            "way": dut.io_install_bits_way,
        }
        self.invalidate = {
            "valid": dut.io_invalidate_valid,
            "idx": dut.io_invalidate_bits_idx,
            "way": dut.io_invalidate_bits_way,
        }
        self.clear = dut.io_clear
        self.spec = []
        for lane in range(3):
            # Only valid/candidate are routed to the DCache top; resident,
            # pending and mshr_id remain internal classification signals.
            self.spec.append({
                "valid": getattr(dut, f"io_spec_{lane}_valid"),
                "candidate": getattr(dut, f"io_spec_{lane}_candidate"),
            })
        self.cycles = 0

    @staticmethod
    def _val(signal) -> int:
        return int(signal.value)

    def _drive(self, loads, allocs, owners, install, invalidate, clear) -> None:
        for lane, load in enumerate(loads):
            pins = self.loads[lane]
            for name in ("s0_valid", "s1_valid", "s2_valid", "s2_hit"):
                pins[name].Set(1 if getattr(load, name) else 0)
            pins["s0_vaddr"].Set(load.s0_vaddr)
            pins["s1_paddr"].Set(load.s1_paddr)
            pins["s2_vaddr"].Set(load.s2_vaddr)
            pins["s2_paddr"].Set(load.s2_paddr)
            pins["s2_way"].Set(load.s2_way)
        for port, alloc in enumerate(allocs):
            pins = self.allocs[port]
            pins["valid"].Set(1 if alloc.valid else 0)
            pins["vaddr"].Set(alloc.vaddr)
            pins["paddr"].Set(alloc.paddr)
            pins["mshr_id"].Set(alloc.mshr_id)
        for slot, owner in enumerate(owners):
            pins = self.owners[slot]
            pins["valid"].Set(1 if owner.valid else 0)
            pins["vaddr"].Set(owner.vaddr)
            pins["paddr"].Set(owner.paddr)
        self.install["valid"].Set(1 if install.valid else 0)
        self.install["vaddr"].Set(install.vaddr)
        self.install["paddr"].Set(install.paddr)
        self.install["way"].Set(install.way)
        self.invalidate["valid"].Set(1 if invalidate.valid else 0)
        self.invalidate["idx"].Set(invalidate.idx)
        self.invalidate["way"].Set(invalidate.way)
        self.clear.Set(1 if clear else 0)

    def _read_spec(self, lane: int) -> Spec:
        pins = self.spec[lane]
        return Spec(valid=self._val(pins["valid"]),
                    candidate=self._val(pins["candidate"]))

    @staticmethod
    def spec_tuple(spec: Spec) -> tuple[int, int]:
        return (spec.valid, spec.candidate)

    def cycle(self, *, loads=None, allocs=None, owners=None, install=Install(),
              invalidate=Invalidate(), clear: bool = False,
              context: str = "cycle") -> list[Spec]:
        loads = loads or [Load(), Load(), Load()]
        allocs = allocs or [Alloc() for _ in range(4)]
        owners = owners if owners is not None else [Owner() for _ in range(16)]
        self._drive(loads, allocs, owners, install, invalidate, clear)
        expected = self.model.cycle(loads, allocs, owners, install, invalidate, clear)
        self.dut.Step(1)
        got = [self._read_spec(lane) for lane in range(3)]
        for lane, (want, actual) in enumerate(zip(expected, got)):
            if self.spec_tuple(want) != self.spec_tuple(actual):
                raise AssertionError(
                    f"{context}: lane {lane} spec {self.spec_tuple(actual)} != "
                    f"{self.spec_tuple(want)}; table="
                    f"{[(e.valid, e.idx, e.block_paddr, e.is_pending, e.age) for e in self.model.entries if e.valid]}")
        if self.coverage is not None:
            for lane, spec in enumerate(got):
                self.coverage.sample_spec(lane, spec, loads[lane])
            self.coverage.sample_events(install, allocs, loads, invalidate, clear,
                                        self.model)
        self.cycles += 1
        return got

    def reset(self) -> None:
        self.dut.reset.Set(1)
        self.dut.Step(2)
        self.dut.reset.Set(0)
        self.dut.Step(2)
        self.model = MissTrackModel()
        self.dut.reset.Set(0)

    # ---------------------------------------------------------------- cases
    def query(self, vaddr: int, paddr: int, lane: int = 0, *, clear: bool = False,
              expected: str | None = None, context: str = "query", owners=None):
        """Issue one S0 query, then present its S1 payload on the next cycle."""
        loads = [Load() for _ in range(3)]
        loads[lane] = Load(s0_valid=True, s0_vaddr=vaddr)
        self.cycle(loads=loads, clear=clear, owners=owners, context=f"{context} s0")
        loads[lane] = Load(s1_valid=True, s1_paddr=paddr)
        spec = self.cycle(loads=loads, owners=owners, context=f"{context} s1")[lane]
        if expected in ("resident", "pending"):
            assert spec.valid and not spec.candidate, (context, spec)
        elif expected == "candidate":
            assert spec.valid and spec.candidate, (context, spec)
        elif expected == "suppressed":
            assert spec.valid == 0, (context, spec)
        return spec
