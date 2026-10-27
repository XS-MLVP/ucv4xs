"""Standalone LLPTW environment with page-table memory and bitmap responders."""
from __future__ import annotations

from dataclasses import dataclass

from toffee import RisingEdge

from mmuverify.l2.l2tlb import PageMemory, pte


@dataclass
class LlpReq:
    vpn: int
    ppn: int
    s2xlate: int = 0
    source: int = 0
    ptes: list[int] | None = None
    cfs: int = 0
    jmp_bitmap: int = 0
    hitway: int = 0


class LlptwEnv:
    def __init__(self, dut, coverage=None) -> None:
        self.dut = dut
        self.coverage = coverage
        self.memory = PageMemory()
        self.tick = 0
        self.mem_requests: list[dict] = []
        self.hptw_requests: list[dict] = []
        self.bitmap_requests: list[dict] = []
        self.cache_requests: list[dict] = []
        self.outs: list[dict] = []
        self._pending_mem: list[tuple[int, int]] = []
        self._bitmap_pending = False
        self._bitmap_queue = []
        self._hptw_counts = {}
        self._monitor_enabled = False
        self.hptw_enabled = False
        self.hptw_gpf = 0
        self.hptw_gaf = 0
        self.hptw_gpf_last = 0
        self.hptw_gaf_last = 0
        self.hptw_perm = dict(r=1, w=1, x=1, a=1, d=1)
        self.hptw_resp_count = 0
        self.trace_events: list[tuple] = []
        self.hptw_resp_gap = 0
        self.hptw_resp_latency = 0
        self._hptw_wait = 0
        self._hptw_cooldown = 0
        self._hptw_queue: list[tuple[int, int]] = []
        self._hptw_resp: tuple[int, int] | None = None
        self.bitmap_cf = 0
        self.bitmap_cfs_value = 0
        d = dut
        self.csr = dict(
            hgatp_mode=d.io_csr_hgatp_mode,
            hgatp_changed=d.io_csr_hgatp_changed,
            satp_changed=d.io_csr_satp_changed,
            vsatp_changed=d.io_csr_vsatp_changed,
            virt_changed=d.io_csr_priv_virt_changed,
            bme=d.io_csr_mbmc_BME,
            cmode=d.io_csr_mbmc_CMODE,
            mxr=d.io_csr_priv_mxr,
            mpbmte=d.io_csr_mPBMTE,
            hpbmte=d.io_csr_hPBMTE,
        )
        self.sfence = d.io_sfence_valid
        self.inp = dict(valid=d.io_in_valid, ready=d.io_in_ready,
                        vpn=d.io_in_bits_req_info_vpn,
                        s2xlate=d.io_in_bits_req_info_s2xlate,
                        source=d.io_in_bits_req_info_source,
                        ppn=d.io_in_bits_ppn,
                        jmp_bitmap=d.io_in_bits_bitmapCheck_jmp_bitmap_check,
                        hitway=d.io_in_bits_bitmapCheck_hitway)
        self.in_ptes = [getattr(d, f"io_in_bits_bitmapCheck_ptes_{i}") for i in range(8)]
        self.in_cfs = [getattr(d, f"io_in_bits_bitmapCheck_cfs_{i}") for i in range(8)]
        self.out = dict(valid=d.io_out_valid, ready=d.io_out_ready,
                        vpn=d.io_out_bits_req_info_vpn,
                        s2xlate=d.io_out_bits_req_info_s2xlate,
                        source=d.io_out_bits_req_info_source,
                        id=d.io_out_bits_id,
                        first_s2_fault=d.io_out_bits_first_s2xlate_fault,
                        af=d.io_out_bits_af,
                        jmp_bitmap=d.io_out_bits_bitmapCheck_jmp_bitmap_check)
        self.out_ptes = [getattr(d, f"io_out_bits_bitmapCheck_ptes_{i}") for i in range(8)]
        self.out_cfs = [getattr(d, f"io_out_bits_bitmapCheck_cfs_{i}") for i in range(8)]
        self.hresp = dict(
            tag=d.io_out_bits_h_resp_entry_tag, vmid=d.io_out_bits_h_resp_entry_vmid,
            n=d.io_out_bits_h_resp_entry_n, pbmt=d.io_out_bits_h_resp_entry_pbmt,
            ppn=d.io_out_bits_h_resp_entry_ppn,
            perm_r=d.io_out_bits_h_resp_entry_perm_r,
            perm_w=d.io_out_bits_h_resp_entry_perm_w,
            perm_x=d.io_out_bits_h_resp_entry_perm_x,
            perm_a=d.io_out_bits_h_resp_entry_perm_a,
            perm_d=d.io_out_bits_h_resp_entry_perm_d,
            level=d.io_out_bits_h_resp_entry_level,
            gpf=d.io_out_bits_h_resp_gpf, gaf=d.io_out_bits_h_resp_gaf,
        )
        self.mem = dict(ready=d.io_mem_req_ready, valid=d.io_mem_req_valid,
                        addr=d.io_mem_req_bits_addr, id=d.io_mem_req_bits_id,
                        resp_valid=d.io_mem_resp_valid, resp_id=d.io_mem_resp_bits_id,
                        resp_value=d.io_mem_resp_bits_value,
                        enq_ptr=d.io_mem_enq_ptr,
                        refill_vpn=d.io_mem_refill_vpn,
                        refill_s2xlate=d.io_mem_refill_s2xlate,
                        refill_source=d.io_mem_refill_source)
        self.masks = [getattr(d, f"io_mem_req_mask_{i}") for i in range(6)]
        self.flush_latches = [getattr(d, f"io_mem_flush_latch_{i}") for i in range(6)]
        self.buffer_it = [getattr(d, f"io_mem_buffer_it_{i}") for i in range(6)]
        self.cache = dict(ready=d.io_cache_ready, valid=d.io_cache_valid,
                          vpn=d.io_cache_bits_vpn, s2xlate=d.io_cache_bits_s2xlate,
                          source=d.io_cache_bits_source)
        self.pmp = [
            dict(addr=d.io_pmp_0_req_bits_addr, ld=d.io_pmp_0_resp_ld,
                 mmio=d.io_pmp_0_resp_mmio),
            dict(addr=d.io_pmp_1_req_bits_addr, ld=d.io_pmp_1_resp_ld,
                 mmio=d.io_pmp_1_resp_mmio),
        ]
        self.hptw = dict(valid=d.io_hptw_req_valid, ready=d.io_hptw_req_ready,
                         source=d.io_hptw_req_bits_source,
                         id=d.io_hptw_req_bits_id, gvpn=d.io_hptw_req_bits_gvpn,
                         resp_valid=d.io_hptw_resp_valid,
                         resp_id=d.io_hptw_resp_bits_id,
                         resp_gpf=d.io_hptw_resp_bits_h_resp_gpf,
                         resp_gaf=d.io_hptw_resp_bits_h_resp_gaf,
                         resp_tag=d.io_hptw_resp_bits_h_resp_entry_tag,
                         resp_ppn=d.io_hptw_resp_bits_h_resp_entry_ppn,
                         resp_level=d.io_hptw_resp_bits_h_resp_entry_level,
                         resp_perm_r=d.io_hptw_resp_bits_h_resp_entry_perm_r,
                         resp_perm_w=d.io_hptw_resp_bits_h_resp_entry_perm_w,
                         resp_perm_x=d.io_hptw_resp_bits_h_resp_entry_perm_x,
                         resp_perm_a=d.io_hptw_resp_bits_h_resp_entry_perm_a,
                         resp_perm_d=d.io_hptw_resp_bits_h_resp_entry_perm_d)
        self.bitmap = dict(valid=d.io_bitmap_req_valid, ready=d.io_bitmap_req_ready,
                           bmppn=d.io_bitmap_req_bits_bmppn,
                           id=d.io_bitmap_req_bits_id,
                           vpn=d.io_bitmap_req_bits_vpn,
                           way_info=d.io_bitmap_req_bits_way_info,
                           n=d.io_bitmap_req_bits_n,
                           s2xlate=d.io_bitmap_req_bits_s2xlate,
                           resp_ready=d.io_bitmap_resp_ready,
                           resp_valid=d.io_bitmap_resp_valid,
                           resp_cf=d.io_bitmap_resp_bits_cf,
                           resp_id=d.io_bitmap_resp_bits_id)
        self.bitmap_cfs = [getattr(d, f"io_bitmap_resp_bits_cfs_{i}") for i in range(8)]
        self.l0_way_info = d.io_l0_way_info

    async def edge(self) -> None:
        self.dut.RefreshComb()
        if self._monitor_enabled:
            self._capture_fires()
        await RisingEdge(self.dut.clock)
        self.tick += 1

    def _capture_fires(self) -> None:
        if self.read(self.inp["valid"]) and self.read(self.inp["ready"]):
            self._hptw_counts.pop(self.read(self.mem["enq_ptr"]), None)
        # Independent channels may fire on the same edge. A priority/continue
        # service chain loses requests on every other ready-high channel.
        for channel, records, fields in (
            (self.cache, self.cache_requests, ("vpn", "s2xlate", "source")),
            (self.bitmap, self.bitmap_requests,
             ("bmppn", "id", "vpn", "way_info", "n", "s2xlate")),
            (self.hptw, self.hptw_requests, ("gvpn", "id", "source")),
            (self.mem, self.mem_requests, ("addr", "id")),
        ):
            if not (self.read(channel["valid"]) and self.read(channel["ready"])):
                continue
            item = {key: self.read(channel[key]) for key in fields}
            records.append(item)
            if channel is self.bitmap:
                self._bitmap_queue.append(item)
            elif channel is self.hptw and self.hptw_enabled:
                rid = item["id"]
                phase = self._hptw_counts.get(rid, 0)
                self._hptw_counts[rid] = phase + 1
                self._hptw_queue.append((self.tick + 2 + self.hptw_resp_latency,
                                         rid, item["gvpn"], phase))
                self.trace_events.append(("hreq", self.tick, rid, item["gvpn"]))
            elif channel is self.mem:
                self._pending_mem.append((item["id"], self._block(item["addr"])))
                self.trace_events.append(("mreq", self.tick, item["id"], item["addr"]))

    def read(self, signal) -> int:
        return int(signal.value)

    async def reset(self) -> None:
        self._monitor_enabled = False
        self._bitmap_queue.clear()
        self._hptw_counts.clear()
        self._bitmap_pending = False
        for name, sig in self.inp.items():
            if name != "ready":
                sig.Set(0)
        for sig in self.in_ptes + self.in_cfs:
            sig.Set(0)
        for sig in self.csr.values():
            sig.Set(0)
        self.sfence.Set(0)
        self.out["ready"].Set(0)
        self.mem["ready"].Set(1)
        self.mem["resp_valid"].Set(0)
        self.mem["resp_id"].Set(0)
        self.mem["resp_value"].Set(0)
        for sig in self.masks:
            sig.Set(0)
        for sig in self.flush_latches:
            sig.Set(0)
        for entry in self.pmp:
            entry["ld"].Set(0)
            entry["mmio"].Set(0)
        self.hptw["ready"].Set(0)
        self.hptw["resp_valid"].Set(0)
        self.hptw_resp_count = 0
        self.trace_events: list[tuple] = []
        self.hptw_resp_gap = 0
        self.hptw_resp_latency = 0
        self._hptw_wait = 0
        self._hptw_cooldown = 0
        self.bitmap["ready"].Set(1)
        self.bitmap["resp_valid"].Set(0)
        self.bitmap["resp_cf"].Set(0)
        self.bitmap["resp_id"].Set(0)
        for sig in self.bitmap_cfs:
            sig.Set(0)
        self.cache["ready"].Set(1)
        self.l0_way_info.Set(0)
        self.mem_requests.clear()
        self.hptw_requests.clear()
        self.trace_events.clear()
        self.bitmap_requests.clear()
        self.cache_requests.clear()
        self.outs.clear()
        self._pending_mem.clear()
        self._hptw_queue.clear()
        self._hptw_resp = None
        self.dut.reset.Set(1)
        await self.edge()
        await self.edge()
        self.dut.reset.Set(0)
        self.sfence.Set(1)
        await self.edge()
        await self.edge()
        self.sfence.Set(0)
        await self.edge()
        self._monitor_enabled = True

    async def issue(self, req: LlpReq) -> None:
        for _ in range(2000):
            self.dut.RefreshComb()
            if self.read(self.inp["ready"]):
                break
            await self.service(1)
        else:
            raise TimeoutError("LLPTW: input ready timeout")
        self.inp["valid"].Set(1)
        self.inp["vpn"].Set(req.vpn)
        self.inp["s2xlate"].Set(req.s2xlate)
        self.inp["source"].Set(req.source)
        self.inp["ppn"].Set(req.ppn)
        self.inp["jmp_bitmap"].Set(req.jmp_bitmap)
        self.inp["hitway"].Set(req.hitway)
        for index in range(8):
            self.in_ptes[index].Set(req.ptes[index] if req.ptes else 0)
            self.in_cfs[index].Set((req.cfs >> index) & 1)
        self.dut.RefreshComb()
        assert self.read(self.inp["ready"]), "LLPTW request not accepted"
        await self.edge()
        self.inp["valid"].Set(0)

    def _block(self, address: int) -> int:
        base = address & ~0x3F
        lo = self.memory.read(base, 32)
        hi = self.memory.read(base + 32, 32)
        return lo | (hi << 256)

    async def service(self, cycles: int) -> int:
        before = len(self.mem_requests)
        for _ in range(cycles):
            self.mem["resp_valid"].Set(0)
            self.hptw["resp_valid"].Set(0)
            self.bitmap["resp_valid"].Set(0)
            if self._pending_mem:
                rid, value = self._pending_mem.pop(0)
                self.mem["resp_valid"].Set(1)
                self.mem["resp_id"].Set(rid)
                self.mem["resp_value"].Set(value)
                self.trace_events.append(("mresp", self.tick, rid))
            if self._hptw_cooldown:
                self._hptw_cooldown -= 1
            elif self._hptw_queue and self._hptw_queue[0][0] <= self.tick:
                _, rid, gvpn, phase = self._hptw_queue.pop(0)
                self.hptw["resp_valid"].Set(1)
                self.hptw["resp_id"].Set(rid)
                self.hptw["resp_tag"].Set(gvpn)
                self.hptw["resp_ppn"].Set(gvpn)
                self.hptw["resp_level"].Set(0)
                self.hptw["resp_gpf"].Set(self.hptw_gpf or (phase > 0 and self.hptw_gpf_last))
                self.hptw["resp_gaf"].Set(self.hptw_gaf or (phase > 0 and self.hptw_gaf_last))
                for key, value in self.hptw_perm.items():
                    self.hptw["resp_perm_" + key].Set(value)
                self.hptw_resp_count += 1
                self._hptw_cooldown = self.hptw_resp_gap
                self.trace_events.append(("hresp", self.tick, rid))
            if self._bitmap_queue:
                item = self._bitmap_queue[0]
                self.bitmap["resp_valid"].Set(1)
                self.bitmap["resp_cf"].Set(self.bitmap_cf)
                self.bitmap["resp_id"].Set(item["id"])
                for index, sig in enumerate(self.bitmap_cfs):
                    sig.Set((self.bitmap_cfs_value >> index) & 1)
                self.dut.RefreshComb()
                if self.read(self.bitmap["resp_ready"]):
                    self._bitmap_queue.pop(0)
            await self.edge()
            self.mem["resp_valid"].Set(0)
            self.hptw["resp_valid"].Set(0)
            self.bitmap["resp_valid"].Set(0)
        return len(self.mem_requests) - before

    async def wait_out(self, max_cycles: int = 200, note: str = "") -> dict:
        self.out["ready"].Set(0)
        for _ in range(max_cycles):
            await self.service(1)
            if self.read(self.out["valid"]):
                snap = {key: self.read(sig) for key, sig in self.out.items()}
                snap["ptes"] = [self.read(sig) for sig in self.out_ptes]
                snap["cfs"] = [self.read(sig) for sig in self.out_cfs]
                snap["h"] = {key: self.read(sig) for key, sig in self.hresp.items()}
                self.out["ready"].Set(1)
                await self.edge()
                self.out["ready"].Set(0)
                return snap
        raise TimeoutError(f"{note}: no LLPTW out; mem={[hex(r['addr']) for r in self.mem_requests]}")
