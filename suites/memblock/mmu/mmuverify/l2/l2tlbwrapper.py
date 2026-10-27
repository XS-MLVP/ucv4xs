"""Env for the L2TLBWrapper combination DUT.

The wrapper connects every L2TLB port 1:1 and adds a two-stage register
delay on the 19 performance-event outputs.  Translation stimulus is shared
with the L2TLB env; this class adds the wrapper-level perf observation.
"""
from __future__ import annotations

from mmuverify.l2.l2tlb import L2TlbEnv


class L2TlbWrapperEnv(L2TlbEnv):
    def __init__(self, dut, coverage=None) -> None:
        super().__init__(dut, coverage)
        self.perf = [getattr(dut, f"io_perf_{index}_value") for index in range(19)]
        self.wfi = dict(req=dut.io_wfi_wfiReq, safe=dut.io_wfi_wfiSafe)
        # Keep the MBIST/DFT boundary quiescent.  These inputs exist in the
        # generated top but are not part of the functional TLB path.
        self.bist = {}
        for name, signal in vars(dut).items():
            if name.startswith(("boreChildrenBd_", "sigFromSrams_", "cg_bore")):
                self.bist[name] = signal

    def perf_values(self) -> list[int]:
        return [self.read(signal) for signal in self.perf]

    def perf_delta(self, before: list[int], after: list[int]) -> list[int]:
        return [(b - a) & 0x3F for a, b in zip(before, after)]

    async def reset(self) -> None:
        for signal in self.bist.values():
            if name_is_input(signal):
                signal.Set(0)
        self.wfi["req"].Set(0)
        await super().reset()

    async def settle_perf(self, cycles: int = 4) -> None:
        for _ in range(cycles):
            await self.edge()
        self.dut.RefreshComb()


def name_is_input(signal) -> bool:
    try:
        return signal.IsInIO() and not signal.IsOutIO()
    except Exception:
        return False
