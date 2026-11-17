"""Standalone bitmapcache environment and port adaptation."""
from __future__ import annotations

from toffee import RisingEdge


class BitmapCacheEnv:
    def __init__(self, dut, coverage=None) -> None:
        self.dut = dut
        self.coverage = coverage
        self.tick = 0
        d = dut
        self.csr = dict(
            satp_changed=d.io_csr_satp_changed,
            vsatp_changed=d.io_csr_vsatp_changed,
            hgatp_changed=d.io_csr_hgatp_changed,
            bclear=d.io_csr_mbmc_BCLEAR,
            virt_changed=d.io_csr_priv_virt_changed,
        )
        self.sfence = d.io_sfence_valid
        self.req = dict(valid=d.io_req_valid, ready=d.io_req_ready,
                        order=d.io_req_bits_order, tag=d.io_req_bits_tag)
        self.resp = dict(valid=d.io_resp_valid, ready=d.io_resp_ready,
                         hit=d.io_resp_bits_hit,
                         order=d.io_resp_bits_order)
        self.cfs = [getattr(d, f"io_resp_bits_cfs_{i}") for i in range(8)]
        self.refill = dict(valid=d.io_refill_valid, tag=d.io_refill_bits_tag,
                           data=d.io_refill_bits_data)

    async def edge(self) -> None:
        await RisingEdge(self.dut.clock)
        self.tick += 1

    def read(self, signal) -> int:
        return int(signal.value)

    async def reset(self) -> None:
        self.req["valid"].Set(0)
        self.resp["ready"].Set(0)
        self.refill["valid"].Set(0)
        self.refill["tag"].Set(0)
        self.refill["data"].Set(0)
        self.sfence.Set(0)
        for signal in self.csr.values():
            signal.Set(0)
        self.dut.reset.Set(1)
        await self.edge()
        await self.edge()
        self.dut.reset.Set(0)
        await self.edge()

    async def send(self, tag: int, order: int = 0) -> None:
        for _ in range(2000):
            self.dut.RefreshComb()
            if self.read(self.req["ready"]):
                break
            await self.edge()
        else:
            raise TimeoutError("Bitmap: input ready timeout")
        self.req["valid"].Set(1)
        self.req["tag"].Set(tag)
        self.req["order"].Set(order)
        await self.edge()
        self.req["valid"].Set(0)

    async def wait_resp(self, max_cycles: int = 40) -> dict:
        self.resp["ready"].Set(1)
        for _ in range(max_cycles):
            await self.edge()
            if self.read(self.resp["valid"]):
                snap = {key: self.read(sig) for key, sig in self.resp.items()}
                snap["cfs"] = [self.read(sig) for sig in self.cfs]
                await self.edge()
                return snap
        raise TimeoutError("BitmapCache: no response")

    async def refill_word(self, tag: int, data: int) -> None:
        if self.coverage is not None:
            self.coverage.sample("refill", (tag >> 3) & 7, 0)
        self.refill["valid"].Set(1)
        self.refill["tag"].Set(tag)
        self.refill["data"].Set(data)
        await self.edge()
        self.refill["valid"].Set(0)
        await self.edge()

    async def pulse_csr_change(self, name: str) -> None:
        """Apply one CSR change pulse for an explicit architectural source."""
        if name not in self.csr:
            raise KeyError(name)
        self.csr[name].Set(1)
        await self.edge()
        self.csr[name].Set(0)
        await self.edge()

    async def pulse_bclear(self) -> None:
        await self.pulse_csr_change("bclear")

    async def pulse_sfence(self, settle: int = 1) -> None:
        self.sfence.Set(1)
        await self.edge()
        self.sfence.Set(0)
        for _ in range(settle):
            await self.edge()

    def set_resp_ready(self, value: int) -> None:
        if value not in (0, 1):
            raise ValueError("response ready must be 0 or 1")
        self.resp["ready"].Set(value)

    def response_valid(self) -> int:
        return self.read(self.resp["valid"])

    def response_snapshot(self) -> dict:
        """Fresh scalar snapshot with a copied ``cfs`` list."""
        return {key: self.read(sig) for key, sig in self.resp.items()} | {
            "cfs": [self.read(sig) for sig in self.cfs]}
