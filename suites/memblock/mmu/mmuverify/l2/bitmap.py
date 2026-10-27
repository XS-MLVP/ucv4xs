"""Env for standalone BitmapCache and Bitmap."""
from __future__ import annotations

from dataclasses import dataclass

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


@dataclass
class BmReq:
    bmppn: int
    vpn: int = 0
    level: int = 0
    n: int = 0
    s2xlate: int = 0
    way_info: int = 0
    hptw_bypassed: int = 0
    id: int = 0


class BitmapEnv:
    def __init__(self, dut, coverage=None) -> None:
        self.dut = dut
        self.coverage = coverage
        self.tick = 0
        self.pmp_deny = False
        self.cache_hit = False
        self.cache_cfs = 0
        self.mem_value = 0
        self.auto_mem = True
        self.auto_cache = True
        self.cache_requests: list[dict] = []
        self.mem_requests: list[dict] = []
        self.resp_order: list[dict] = []
        self.refills: list[dict] = []
        self.wakeup_events: list[dict] = []
        self._refill_prev = False
        self._wakeup_prev = False
        self._mem_active = False
        self._cache_pending: int | None = None
        self._cache_queue = []
        self._mem_queue = []
        self._monitor_enabled = False
        d = dut
        self.csr = dict(
            satp_changed=d.io_csr_satp_changed,
            vsatp_changed=d.io_csr_vsatp_changed,
            hgatp_changed=d.io_csr_hgatp_changed,
            virt_changed=d.io_csr_priv_virt_changed,
            bma=d.io_csr_mbmc_BMA,
        )
        self.sfence = d.io_sfence_valid
        self.req = dict(valid=d.io_req_valid, ready=d.io_req_ready,
                        bmppn=d.io_req_bits_bmppn, id=d.io_req_bits_id,
                        vpn=d.io_req_bits_vpn, level=d.io_req_bits_level,
                        way_info=d.io_req_bits_way_info,
                        hptw_bypassed=d.io_req_bits_hptw_bypassed,
                        s2xlate=d.io_req_bits_s2xlate, n=d.io_req_bits_n)
        self.resp = dict(valid=d.io_resp_valid, ready=d.io_resp_ready,
                         cf=d.io_resp_bits_cf, id=d.io_resp_bits_id)
        self.cfs = [getattr(d, f"io_resp_bits_cfs_{i}") for i in range(8)]
        self.mem = dict(ready=d.io_mem_req_ready, valid=d.io_mem_req_valid,
                        addr=d.io_mem_req_bits_addr, id=d.io_mem_req_bits_id,
                        resp_valid=d.io_mem_resp_valid,
                        resp_id=d.io_mem_resp_bits_id,
                        resp_value=d.io_mem_resp_bits_value,
                        masks=[getattr(d, f"io_mem_req_mask_{i}") for i in range(8)])
        self.pmp = dict(req=d.io_pmp_req_bits_addr, ld=d.io_pmp_resp_ld,
                        mmio=d.io_pmp_resp_mmio)
        self.wakeup = dict(valid=d.io_wakeup_valid, ready=d.io_wakeup_ready,
                           set=d.io_wakeup_bits_setIndex, tag=d.io_wakeup_bits_tag,
                           way=d.io_wakeup_bits_way_info,
                           pteidx=d.io_wakeup_bits_pte_index,
                           ok=d.io_wakeup_bits_check_success,
                           s2xlate=d.io_wakeup_bits_s2xlate)
        self.cache = dict(ready=d.io_cache_req_ready, valid=d.io_cache_req_valid,
                          order=d.io_cache_req_bits_order, tag=d.io_cache_req_bits_tag,
                          resp_ready=d.io_cache_resp_ready,
                          resp_valid=d.io_cache_resp_valid,
                          resp_hit=d.io_cache_resp_bits_hit,
                          resp_order=d.io_cache_resp_bits_order)
        self.cache_cfs_pins = [getattr(d, f"io_cache_resp_bits_cfs_{i}") for i in range(8)]
        self.refill = dict(valid=d.io_refill_valid, tag=d.io_refill_bits_tag,
                           data=d.io_refill_bits_data)

    async def edge(self) -> None:
        self.pmp["ld"].Set(int(self.pmp_deny))
        self.pmp["mmio"].Set(0)
        self.dut.RefreshComb()
        if self._monitor_enabled:
            self.capture_aux()
            if self.read(self.cache["valid"]) and self.read(self.cache["ready"]):
                item = {key: self.read(self.cache[key]) for key in ("tag", "order")}
                self.cache_requests.append(item)
                self._cache_queue.append(item)
            if self.read(self.mem["valid"]) and self.read(self.mem["ready"]):
                item = {key: self.read(self.mem[key]) for key in ("addr", "id")}
                self.mem_requests.append(item)
                self._mem_queue.append((item["id"], self.mem_value))
        await RisingEdge(self.dut.clock)
        self.tick += 1

    def read(self, signal) -> int:
        return int(signal.value)

    async def reset(self) -> None:
        self._monitor_enabled = False
        self._cache_queue.clear()
        self._mem_queue.clear()
        self._cache_pending = None
        self._mem_active = False
        self.cache_requests.clear()
        self.mem_requests.clear()
        self.resp_order.clear()
        self.refills.clear()
        self.wakeup_events.clear()
        for signal in self.mem["masks"]:
            signal.Set(0)
        self.req["valid"].Set(0)
        self.resp["ready"].Set(0)
        self.mem["ready"].Set(1)
        self.mem["resp_valid"].Set(0)
        self.mem["resp_id"].Set(0)
        self.mem["resp_value"].Set(0)
        self.pmp["ld"].Set(0)
        self.pmp["mmio"].Set(0)
        self.wakeup["ready"].Set(0)
        self.cache["ready"].Set(1)
        self.cache["resp_valid"].Set(0)
        self.cache["resp_hit"].Set(0)
        self.cache["resp_order"].Set(0)
        for pin in self.cache_cfs_pins:
            pin.Set(0)
        self.sfence.Set(0)
        for signal in self.csr.values():
            signal.Set(0)
        self.dut.reset.Set(1)
        await self.edge()
        await self.edge()
        self.dut.reset.Set(0)
        await self.edge()
        assert self.read(self.req["ready"]) == 1
        self._monitor_enabled = True

    async def issue(self, req: BmReq) -> None:
        for _ in range(2000):
            self.dut.RefreshComb()
            if self.read(self.req["ready"]):
                break
            await self.edge()
        else:
            raise TimeoutError("Bitmap: input ready timeout")
        self.req["valid"].Set(1)
        self.req["bmppn"].Set(req.bmppn)
        self.req["vpn"].Set(req.vpn)
        self.req["level"].Set(req.level)
        self.req["n"].Set(req.n)
        self.req["s2xlate"].Set(req.s2xlate)
        self.req["way_info"].Set(req.way_info)
        self.req["hptw_bypassed"].Set(req.hptw_bypassed)
        self.req["id"].Set(req.id)
        await self.edge()
        self.req["valid"].Set(0)

    async def service(self, cycles: int) -> int:
        before = len(self.mem_requests)
        for _ in range(cycles):
            self.cache["resp_valid"].Set(0)
            self.mem["resp_valid"].Set(0)
            if self._cache_queue and self.auto_cache:
                item = self._cache_queue[0]
                self.cache["resp_valid"].Set(1)
                self.cache["resp_hit"].Set(int(self.cache_hit))
                self.cache["resp_order"].Set(item["order"])
                for index, pin in enumerate(self.cache_cfs_pins):
                    pin.Set((self.cache_cfs >> index) & 1)
                self.dut.RefreshComb()
                if self.read(self.cache["resp_ready"]):
                    self._cache_queue.pop(0)
            if self._mem_queue and self.auto_mem:
                rid, value = self._mem_queue.pop(0)
                self.mem["resp_valid"].Set(1)
                self.mem["resp_id"].Set(rid)
                self.mem["resp_value"].Set(value)
            await self.edge()
            self.cache["resp_valid"].Set(0)
            self.mem["resp_valid"].Set(0)
        return len(self.mem_requests) - before

    def capture_aux(self) -> None:
        # Refill is Valid-only; adjacent valid cycles are distinct events.
        if self.read(self.refill["valid"]):
            self.refills.append({"tag": self.read(self.refill["tag"]),
                                 "data": self.read(self.refill["data"])})
        if self.read(self.wakeup["valid"]) and self.read(self.wakeup["ready"]):
            self.wakeup_events.append({key: self.read(self.wakeup[key])
                                       for key in ("set", "tag", "way", "pteidx", "ok", "s2xlate")})

    async def wait_resp(self, max_cycles: int = 200, note: str = "") -> dict:
        self.resp["ready"].Set(0)
        for _ in range(max_cycles):
            await self.service(1)
            if self.read(self.resp["valid"]):
                snap = {key: self.read(sig) for key, sig in self.resp.items()}
                snap["cfs"] = [self.read(sig) for sig in self.cfs]
                self.resp_order.append(snap)
                self.resp["ready"].Set(1)
                await self.edge()
                self.resp["ready"].Set(0)
                return snap
        raise TimeoutError(f"{note}: no Bitmap response")
