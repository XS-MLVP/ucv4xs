"""Standalone PtwCache environment."""
from __future__ import annotations

from dataclasses import dataclass

from toffee import RisingEdge

PTE_FIELDS = ("tag", "asid", "vmid", "n", "pbmt", "perm_a", "perm_d", "perm_g",
              "perm_r", "perm_u", "perm_w", "perm_x", "level", "v", "ppn",
              "ppn_low", "pf", "cf")


@dataclass
class CacheReq:
    vpn: int
    s2xlate: int = 0
    source: int = 0
    is_first: int = 1
    is_hptw: int = 0
    hptw_id: int = 0
    bypassed: int = 0


class PtwCacheEnv:
    def __init__(self, dut, coverage=None) -> None:
        self.dut = dut
        self.coverage = coverage
        self.tick = 0
        d = dut
        self.req = dict(
            valid=d.io_req_valid, ready=d.io_req_ready,
            vpn=d.io_req_bits_req_info_vpn,
            s2xlate=d.io_req_bits_req_info_s2xlate,
            source=d.io_req_bits_req_info_source,
            is_first=d.io_req_bits_isFirst,
            is_hptw=d.io_req_bits_isHptwReq,
            hptw_id=d.io_req_bits_hptwId,
        )
        self.resp = dict(
            ready=d.io_resp_ready, valid=d.io_resp_valid,
            vpn=d.io_resp_bits_req_info_vpn,
            s2xlate=d.io_resp_bits_req_info_s2xlate,
            source=d.io_resp_bits_req_info_source,
            is_first=d.io_resp_bits_isFirst,
            hit=d.io_resp_bits_hit,
            prefetch=d.io_resp_bits_prefetch,
            bypassed=d.io_resp_bits_bypassed,
            is_hptw=d.io_resp_bits_isHptwReq,
            l3hit=d.io_resp_bits_toFsm_l3Hit,
            l2hit=d.io_resp_bits_toFsm_l2Hit,
            l1hit=d.io_resp_bits_toFsm_l1Hit,
            ppn=d.io_resp_bits_toFsm_ppn,
            stage1hit=d.io_resp_bits_toFsm_stage1Hit,
            jmp_bitmap=d.io_resp_bits_toFsm_bitmapCheck_jmp_bitmap_check,
            tollptw=d.io_resp_bits_toFsm_bitmapCheck_toLLPTW,
            hitway=d.io_resp_bits_toFsm_bitmapCheck_hitway,
            bitmap_pte=d.io_resp_bits_toFsm_bitmapCheck_pte,
            splevel=d.io_resp_bits_toFsm_bitmapCheck_SPlevel,
            h_bypassed=d.io_resp_bits_toHptw_bypassed,
            h_l3hit=d.io_resp_bits_toHptw_l3Hit,
            h_l2hit=d.io_resp_bits_toHptw_l2Hit,
            h_l1hit=d.io_resp_bits_toHptw_l1Hit,
            h_ppn=d.io_resp_bits_toHptw_ppn,
            h_id=d.io_resp_bits_toHptw_id,
        )
        for index in range(8):
            for field in PTE_FIELDS:
                self.resp[f"e{index}_{field}"] = getattr(
                    d, f"io_resp_bits_stage1_entry_{index}_{field}")
            self.resp[f"pteidx_{index}"] = getattr(
                d, f"io_resp_bits_stage1_pteidx_{index}")
        self.resp["not_super"] = d.io_resp_bits_stage1_not_super
        self.resp["bitmap_cfs"] = [
            getattr(d, f"io_resp_bits_toFsm_bitmapCheck_cfs_{i}") for i in range(8)]
        self.resp["bitmap_ptes"] = [
            getattr(d, f"io_resp_bits_toFsm_bitmapCheck_ptes_{i}") for i in range(8)]
        self.resp["toHptw"] = {
            "tag": d.io_resp_bits_toHptw_resp_entry_tag,
            "ppn": d.io_resp_bits_toHptw_resp_entry_ppn,
            "level": d.io_resp_bits_toHptw_resp_entry_level,
            "pbmt": d.io_resp_bits_toHptw_resp_entry_pbmt,
            "n": d.io_resp_bits_toHptw_resp_entry_n,
            "gpf": d.io_resp_bits_toHptw_resp_gpf,
            "fromSP": d.io_resp_bits_toHptw_bitmapCheck_fromSP,
            "jmp": d.io_resp_bits_toHptw_bitmapCheck_jmp_bitmap_check,
            "splevel": d.io_resp_bits_toHptw_bitmapCheck_SPlevel,
        }
        self.refill = dict(
            valid=d.io_refill_valid,
            l0=d.io_refill_bits_levelOH_l0,
            l1=d.io_refill_bits_levelOH_l1,
            l2=d.io_refill_bits_levelOH_l2,
            l3=d.io_refill_bits_levelOH_l3,
            sp=d.io_refill_bits_levelOH_sp,
            level0=d.io_refill_bits_level_dup_0,
            level2=d.io_refill_bits_level_dup_2,
            ptes=d.io_refill_bits_ptes,
            sel0=d.io_refill_bits_sel_pte_dup_0,
            sel2=d.io_refill_bits_sel_pte_dup_2,
        )
        for index in range(3):
            for field in ("vpn", "s2xlate", "source"):
                name = f"io_refill_bits_req_info_dup_{index}_{field}"
                if hasattr(d, name):
                    self.refill[f"i{index}_{field}"] = getattr(d, name)
        self.l0_way_info = d.io_l0_way_info
        self.sfence = []
        for index in range(3):
            entry = {"valid": getattr(d, f"io_sfence_dup_{index}_valid")}
            if index == 0:
                for field in ("addr", "rs1", "rs2", "id", "hv", "hg"):
                    entry[field] = getattr(d, f"io_sfence_dup_{index}_bits_{field}")
            else:
                entry["id"] = getattr(d, f"io_sfence_dup_{index}_bits_id")
                if index == 2:
                    entry["rs1"] = getattr(d, f"io_sfence_dup_{index}_bits_rs1")
                    entry["rs2"] = getattr(d, f"io_sfence_dup_{index}_bits_rs2")
            self.sfence.append(entry)
        self.csr = []
        for index in range(3):
            entry = {
                "satp_asid": getattr(d, f"io_csr_dup_{index}_satp_asid"),
                "satp_changed": getattr(d, f"io_csr_dup_{index}_satp_changed"),
                "vsatp_asid": getattr(d, f"io_csr_dup_{index}_vsatp_asid"),
                "vsatp_changed": getattr(d, f"io_csr_dup_{index}_vsatp_changed"),
                "hgatp_changed": getattr(d, f"io_csr_dup_{index}_hgatp_changed"),
                "hgatp_mode": getattr(d, f"io_csr_dup_{index}_hgatp_mode"),
                "hgatp_vmid": getattr(d, f"io_csr_dup_{index}_hgatp_vmid"),
                "virt": getattr(d, f"io_csr_dup_{index}_priv_virt"),
                "virt_changed": getattr(d, f"io_csr_dup_{index}_priv_virt_changed"),
            }
            if index == 0:
                entry["bme"] = getattr(d, f"io_csr_dup_{index}_mbmc_BME")
                entry["cmode"] = getattr(d, f"io_csr_dup_{index}_mbmc_CMODE")
            self.csr.append(entry)
        self.wakeup = dict(
            valid=d.io_bitmap_wakeup_valid, ready=d.io_bitmap_wakeup_ready,
            check_success=d.io_bitmap_wakeup_bits_check_success,
            pte_index=d.io_bitmap_wakeup_bits_pte_index,
            s2xlate=d.io_bitmap_wakeup_bits_s2xlate,
            set=d.io_bitmap_wakeup_bits_setIndex,
            tag=d.io_bitmap_wakeup_bits_tag,
            way=d.io_bitmap_wakeup_bits_way_info,
        )

    async def edge(self) -> None:
        await RisingEdge(self.dut.clock)
        self.tick += 1

    def read(self, signal) -> int:
        return int(signal.value)

    def set_csr(self, **values) -> None:
        for index in range(3):
            for key, value in values.items():
                if key in self.csr[index]:
                    self.csr[index][key].Set(value)
        self.dut.RefreshComb()

    async def reset(self) -> None:
        self.req["valid"].Set(0)
        self.resp["ready"].Set(0)
        self.refill["valid"].Set(0)
        for key in ("l0", "l1", "l2", "l3", "sp"):
            self.refill[key].Set(0)
        self.refill["ptes"].Set(0)
        self.refill["sel0"].Set(0)
        self.refill["sel2"].Set(0)
        for index in range(3):
            for field in ("vpn", "s2xlate", "source"):
                key = f"i{index}_{field}"
                if key in self.refill:
                    self.refill[key].Set(0)
        for entry in self.sfence:
            for signal in entry.values():
                signal.Set(0)
        self.set_csr(satp_asid=0, satp_changed=0, vsatp_asid=0, vsatp_changed=0,
                     hgatp_changed=0, hgatp_mode=0, hgatp_vmid=0, virt=0,
                     virt_changed=0, bme=0, cmode=0)
        self.wakeup["valid"].Set(0)
        for key, signal in self.wakeup.items():
            if key != "ready":
                signal.Set(0)
        self.dut.reset.Set(1)
        await self.edge()
        await self.edge()
        self.dut.reset.Set(0)
        await self.edge()
        assert self.read(self.req["ready"]) == 1

    async def issue(self, req: CacheReq) -> None:
        for _ in range(2000):
            self.dut.RefreshComb()
            if self.read(self.req["ready"]):
                break
            await self.edge()
        else:
            raise TimeoutError("PtwCache: input ready timeout")
        self.req["valid"].Set(1)
        self.req["vpn"].Set(req.vpn)
        self.req["s2xlate"].Set(req.s2xlate)
        self.req["source"].Set(req.source)
        self.req["is_first"].Set(req.is_first)
        self.req["is_hptw"].Set(req.is_hptw)
        self.req["hptw_id"].Set(req.hptw_id)
        self.dut.RefreshComb()
        await self.edge()
        self.req["valid"].Set(0)

    def _pte_word(self, ptes: list[int] | None, index: int, selected: int) -> int:
        if ptes is None:
            return selected
        return ptes[index] if index < len(ptes) else selected

    async def refill_entries(self, vpn: int, level: int, ptes: list[int],
                             s2xlate: int = 0, source: int = 0,
                             selected: int | None = None) -> None:
        """Refill one cache level. level 0 = 4KB sector, 1/2/3 = superpage."""
        assert self.read(self.req["ready"]) == 1
        selected = ptes[0] if selected is None else selected
        data = 0
        for index in range(8):
            word = self._pte_word(ptes, index, selected)
            data |= word << (64 * index)
        self.refill["valid"].Set(1)
        for key in ("l0", "l1", "l2", "l3", "sp"):
            self.refill[key].Set(1 if {
                "l0": level == 0, "l1": level == 1, "l2": level == 2,
                "l3": level == 3, "sp": level >= 1}[key] else 0)
        self.refill["level0"].Set(level)
        self.refill["level2"].Set(level)
        self.refill["ptes"].Set(data)
        self.refill["sel0"].Set(selected)
        self.refill["sel2"].Set(selected)
        for index in range(3):
            self.refill[f"i{index}_vpn"].Set(vpn)
            self.refill[f"i{index}_s2xlate"].Set(s2xlate)
            if f"i{index}_source" in self.refill:
                self.refill[f"i{index}_source"].Set(source)
        self.dut.RefreshComb()
        await self.edge()
        self.refill["valid"].Set(0)
        for key in ("l0", "l1", "l2", "l3", "sp"):
            self.refill[key].Set(0)
        await self.edge()
        await self.edge()

    async def refill_l0(self, vpn: int, ptes: list[int], s2xlate: int = 0,
                        source: int = 0) -> None:
        await self.refill_entries(vpn, 0, ptes, s2xlate, source,
                                  selected=ptes[vpn & 7])

    async def refill_super(self, vpn: int, level: int, pte: int,
                           s2xlate: int = 0, source: int = 0) -> None:
        await self.refill_entries(vpn, level, [pte] * 8, s2xlate, source,
                                  selected=pte)

    async def wait_resp(self, max_cycles: int = 40) -> dict:
        self.resp["ready"].Set(0)
        for _ in range(max_cycles):
            await self.edge()
            if self.read(self.resp["valid"]):
                snap = {key: self.read(sig) for key, sig in self.resp.items()
                        if not isinstance(sig, (dict, list))}
                if "bitmap_cfs" not in snap:
                    snap["bitmap_cfs"] = [self.read(sig) for sig in self.resp["bitmap_cfs"]]
                    snap["bitmap_ptes"] = [self.read(sig) for sig in self.resp["bitmap_ptes"]]
                if "toHptw" not in snap:
                    snap["toHptw"] = {k: self.read(v) for k, v in self.resp["toHptw"].items()}
                self.resp["ready"].Set(1)
                await self.edge()
                self.resp["ready"].Set(0)
                return snap
        raise TimeoutError("PtwCache: no response")

    async def flush(self, *, addr: int = 0, rs1: int = 0, rs2: int = 0,
                    asid: int = 0, hv: int = 0, hg: int = 0) -> None:
        for signal in self.sfence[0].values():
            signal.Set(0)
        self.sfence[0]["valid"].Set(1)
        self.sfence[0]["id"].Set(asid)
        self.sfence[0]["addr"].Set(addr)
        self.sfence[0]["rs1"].Set(rs1)
        self.sfence[0]["rs2"].Set(rs2)
        self.sfence[0]["hv"].Set(hv)
        self.sfence[0]["hg"].Set(hg)
        for entry in self.sfence[1:]:
            entry["valid"].Set(1)
            entry["id"].Set(asid)
        self.sfence[2]["rs1"].Set(rs1)
        self.sfence[2]["rs2"].Set(rs2)
        await self.edge()
        for entry in self.sfence:
            entry["valid"].Set(0)
        await self.edge()
        await self.edge()
        await self.edge()
