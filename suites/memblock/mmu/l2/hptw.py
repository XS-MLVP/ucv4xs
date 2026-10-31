"""Standalone HPTW environment with a 64-bit page-table memory responder."""
from __future__ import annotations

from dataclasses import dataclass

from toffee import RisingEdge

from suites.memblock.mmu.l2.l2tlb import PageMemory, pte


@dataclass
class MemReq:
    address: int
    bypassed: int


class HptwEnv:
    def __init__(self, dut, coverage=None) -> None:
        self.dut = dut
        self.coverage = coverage
        self.memory = PageMemory()
        self.tick = 0
        self.requests: list[MemReq] = []
        self._pending: list[tuple[int, int]] = []
        self._bitmap_queue = []
        self._monitor_enabled = False
        self.bitmap_requests: list[int] = []
        d = dut
        self.csr = dict(
            hgatp_mode=d.io_csr_hgatp_mode,
            hgatp_vmid=d.io_csr_hgatp_vmid,
            hgatp_ppn=d.io_csr_hgatp_ppn,
            hgatp_changed=d.io_csr_hgatp_changed,
            satp_changed=d.io_csr_satp_changed,
            vsatp_changed=d.io_csr_vsatp_changed,
            virt_changed=d.io_csr_priv_virt_changed,
            bme=d.io_csr_mbmc_BME,
            cmode=d.io_csr_mbmc_CMODE,
            mpbmte=d.io_csr_mPBMTE,
        )
        self.sfence = d.io_sfence_valid
        self.req = dict(
            ready=d.io_req_ready,
            valid=d.io_req_valid,
            source=d.io_req_bits_source,
            id=d.io_req_bits_id,
            gvpn=d.io_req_bits_gvpn,
            ppn=d.io_req_bits_ppn,
            l3hit=d.io_req_bits_l3Hit,
            l2hit=d.io_req_bits_l2Hit,
            l1hit=d.io_req_bits_l1Hit,
            bypassed=d.io_req_bits_bypassed,
            jmp_bitmap=d.io_req_bits_bitmapCheck_jmp_bitmap_check,
            bitmap_pte=d.io_req_bits_bitmapCheck_pte,
            bitmap_ptes_0=d.io_req_bits_bitmapCheck_ptes_0,
            bitmap_ptes_1=d.io_req_bits_bitmapCheck_ptes_1,
            bitmap_ptes_2=d.io_req_bits_bitmapCheck_ptes_2,
            bitmap_ptes_3=d.io_req_bits_bitmapCheck_ptes_3,
            bitmap_ptes_4=d.io_req_bits_bitmapCheck_ptes_4,
            bitmap_ptes_5=d.io_req_bits_bitmapCheck_ptes_5,
            bitmap_ptes_6=d.io_req_bits_bitmapCheck_ptes_6,
            bitmap_ptes_7=d.io_req_bits_bitmapCheck_ptes_7,
            bitmap_hitway=d.io_req_bits_bitmapCheck_hitway,
            bitmap_fromsp=d.io_req_bits_bitmapCheck_fromSP,
            bitmap_splevel=d.io_req_bits_bitmapCheck_SPlevel,
        )
        self.resp = dict(
            ready=d.io_resp_ready,
            valid=d.io_resp_valid,
            tag=d.io_resp_bits_resp_entry_tag,
            vmid=d.io_resp_bits_resp_entry_vmid,
            n=d.io_resp_bits_resp_entry_n,
            pbmt=d.io_resp_bits_resp_entry_pbmt,
            ppn=d.io_resp_bits_resp_entry_ppn,
            perm_d=d.io_resp_bits_resp_entry_perm_d,
            perm_a=d.io_resp_bits_resp_entry_perm_a,
            perm_x=d.io_resp_bits_resp_entry_perm_x,
            perm_w=d.io_resp_bits_resp_entry_perm_w,
            perm_r=d.io_resp_bits_resp_entry_perm_r,
            level=d.io_resp_bits_resp_entry_level,
            gpf=d.io_resp_bits_resp_gpf,
            gaf=d.io_resp_bits_resp_gaf,
            id=d.io_resp_bits_id,
        )
        self.mem_req = dict(
            ready=d.io_mem_req_ready,
            valid=d.io_mem_req_valid,
            addr=d.io_mem_req_bits_addr,
            bypassed=d.io_mem_req_bits_hptw_bypassed,
        )
        self.mem_resp = dict(valid=d.io_mem_resp_valid, bits=d.io_mem_resp_bits)
        self.mem_mask = d.io_mem_mask
        self.pmp = dict(ld=d.io_pmp_resp_ld, mmio=d.io_pmp_resp_mmio,
                        req=d.io_pmp_req_bits_addr)
        self.bitmap = dict(
            req_ready=d.io_bitmap_req_ready,
            req_valid=d.io_bitmap_req_valid,
            req_bmppn=d.io_bitmap_req_bits_bmppn,
            req_vpn=d.io_bitmap_req_bits_vpn,
            req_level=d.io_bitmap_req_bits_level,
            resp_ready=d.io_bitmap_resp_ready,
            resp_valid=d.io_bitmap_resp_valid,
            resp_cf=d.io_bitmap_resp_bits_cf,
        )
        self.refill = dict(
            vpn=d.io_refill_req_info_vpn,
            source=d.io_refill_req_info_source,
            level=d.io_refill_level,
        )

    async def edge(self) -> None:
        self.dut.RefreshComb()
        if self._monitor_enabled:
            if self.read(self.mem_req["valid"]) and self.read(self.mem_req["ready"]):
                address = self.read(self.mem_req["addr"])
                self.requests.append(MemReq(address, self.read(self.mem_req["bypassed"])))
                self._pending.append((address, self.memory.read(address & ~7, 8)))
            if self.read(self.bitmap["req_valid"]) and self.read(self.bitmap["req_ready"]):
                ppn = self.read(self.bitmap["req_bmppn"])
                self.bitmap_requests.append(ppn)
                self._bitmap_queue.append(ppn)
        await RisingEdge(self.dut.clock)
        self.tick += 1

    def read(self, signal) -> int:
        return int(signal.value)

    async def reset(self, post_sfence: bool = True) -> None:
        self._monitor_enabled = False
        self._pending.clear()
        self._bitmap_queue.clear()
        self.requests.clear()
        self.bitmap_requests.clear()
        for key, signal in self.req.items():
            if key != "ready":
                signal.Set(0)
        for signal in self.csr.values():
            signal.Set(0)
        self.sfence.Set(0)
        self.resp["ready"].Set(0)
        self.mem_req["ready"].Set(1)
        self.mem_resp["valid"].Set(0)
        self.mem_resp["bits"].Set(0)
        self.mem_mask.Set(0)
        self.pmp["ld"].Set(0)
        self.pmp["mmio"].Set(0)
        self.bitmap["req_ready"].Set(1)
        self.bitmap["resp_valid"].Set(0)
        self.bitmap["resp_cf"].Set(0)
        self.dut.reset.Set(1)
        await self.edge()
        await self.edge()
        self.dut.reset.Set(0)
        # accessFault is only cleared by flush, not by the synchronous reset.
        if post_sfence:
            self.sfence.Set(1)
            await self.edge()
            await self.edge()
            self.sfence.Set(0)
            await self.edge()
        else:
            await self.edge()
        assert self.read(self.req["ready"]) == 1
        self._monitor_enabled = True

    async def issue(self, gvpn: int, *, ppn: int = 0, l3hit: int = 0,
                    l2hit: int = 0, l1hit: int = 0, source: int = 0,
                    id: int = 0, bypassed: int = 0,
                    jmp_bitmap: int = 0, bitmap_pte: int = 0,
                    bitmap_ptes: list[int] | None = None,
                    bitmap_hitway: int = 0,
                    bitmap_fromsp: int = 0, bitmap_splevel: int = 0) -> None:
        assert self.read(self.req["ready"]) == 1
        self.req["valid"].Set(1)
        self.req["gvpn"].Set(gvpn)
        self.req["ppn"].Set(ppn)
        self.req["l3hit"].Set(l3hit)
        self.req["l2hit"].Set(l2hit)
        self.req["l1hit"].Set(l1hit)
        self.req["source"].Set(source)
        self.req["id"].Set(id)
        self.req["bypassed"].Set(bypassed)
        self.req["jmp_bitmap"].Set(jmp_bitmap)
        self.req["bitmap_pte"].Set(bitmap_pte)
        for index in range(8):
            self.req[f"bitmap_ptes_{index}"].Set(
                bitmap_ptes[index] if bitmap_ptes else 0)
        self.req["bitmap_hitway"].Set(bitmap_hitway)
        self.req["bitmap_fromsp"].Set(bitmap_fromsp)
        self.req["bitmap_splevel"].Set(bitmap_splevel)
        await self.edge()
        self.req["valid"].Set(0)

    async def service_memory(self, cycles: int, mask: int = 0) -> int:
        before = len(self.requests)
        for _ in range(cycles):
            self.mem_resp["valid"].Set(0)
            self.bitmap["resp_valid"].Set(0)
            if self._pending:
                _, value = self._pending.pop(0)
                self.mem_resp["valid"].Set(1)
                self.mem_resp["bits"].Set(value)
            if self._bitmap_queue:
                self.bitmap["resp_valid"].Set(1)
                self.bitmap["resp_cf"].Set(0)
                self.dut.RefreshComb()
                if self.read(self.bitmap["resp_ready"]):
                    self._bitmap_queue.pop(0)
            await self.edge()
            self.mem_resp["valid"].Set(0)
            self.bitmap["resp_valid"].Set(0)
        return len(self.requests) - before

    async def wait_response(self, max_cycles: int = 2000, note: str = "") -> dict:
        self.resp["ready"].Set(0)
        for _ in range(max_cycles):
            await self.service_memory(1)
            if self.read(self.resp["valid"]):
                snap = {key: self.read(signal) for key, signal in self.resp.items()}
                if self.coverage is not None:
                    self.sample_response(snap)
                self.resp["ready"].Set(1)
                await self.edge()
                self.resp["ready"].Set(0)
                return snap
        raise TimeoutError(f"{note}: no HPTW response; requests={[(hex(r.address)) for r in self.requests]}")

    def sample_response(self, snap: dict) -> None:
        if snap.get("gpf") or snap.get("gaf"):
            self.coverage.sample("fault", page="fault")
        else:
            page = {2: "1g", 1: "2m", 0: "4k"}.get(snap.get("level"), "4k")
            self.coverage.sample("walk", page=page)

    def build_sv39_gstage(self, root_ppn: int, gvpn: int, final_ppn: int,
                          mid_ppn: int | None = None, leaf_ppn: int | None = None,
                          level: int = 0, **perms) -> None:
        """Install a G-stage page table. Leaves use U=1 as HPTW requires."""
        perms = perms or dict(r=1, w=1, x=1, u=1, a=1, d=1)
        self.memory.build_sv39(root_ppn, gvpn, final_ppn, level=level,
                               perms=perms, mid_ppn=mid_ppn, leaf_ppn=leaf_ppn)
