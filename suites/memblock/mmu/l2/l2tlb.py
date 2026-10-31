"""Env for the L2TLB top level with a simple page-table memory responder."""
from __future__ import annotations

from dataclasses import dataclass

from toffee import RisingEdge


def pte(ppn: int, *, v: int = 1, r: int = 0, w: int = 0, x: int = 0,
        u: int = 0, g: int = 0, a: int = 1, d: int = 1, pbmt: int = 0,
        n: int = 0) -> int:
    value = (ppn & ((1 << 44) - 1)) << 10
    value |= (pbmt & 0x3) << 61
    value |= (n & 1) << 63
    value |= (d & 1) << 7
    value |= (a & 1) << 6
    value |= (g & 1) << 5
    value |= (u & 1) << 4
    value |= (x & 1) << 3
    value |= (w & 1) << 2
    value |= (r & 1) << 1
    value |= v & 1
    return value


class PageMemory:
    """Sparse byte-addressable memory used as the page-table backing store."""

    def __init__(self) -> None:
        self.data: dict[int, int] = {}

    def write(self, addr: int, value: int, width: int = 8) -> None:
        for index in range(width):
            self.data[addr + index] = (value >> (8 * index)) & 0xFF

    def read(self, addr: int, width: int = 8) -> int:
        value = 0
        for index in range(width):
            value |= self.data.get(addr + index, 0) << (8 * index)
        return value

    def block(self, addr: int, size: int) -> int:
        width = 1 << size
        base = addr & ~(width - 1)
        return self.read(base, min(width, 32))

    def build_sv39(self, root_ppn: int, vpn: int, final_ppn: int,
                   level: int = 0, perms: dict | None = None,
                   mid_ppn: int | None = None,
                   leaf_ppn: int | None = None) -> None:
        """Install a Sv39 chain: root -> mid -> (leaf at requested level)."""
        perms = perms or dict(r=1, w=1, x=1, u=1, a=1, d=1)
        vpn1 = (vpn >> 18) & 0x1FF
        vpn0 = (vpn >> 9) & 0x1FF
        vpn_leaf = vpn & 0x1FF
        mid_ppn = ((mid_ppn if mid_ppn is not None else root_ppn + 1)
                   & ((1 << 44) - 1))
        leaf_table_ppn = ((leaf_ppn if leaf_ppn is not None else root_ppn + 2)
                          & ((1 << 44) - 1))
        if level >= 2:
            self.write((root_ppn << 12) + vpn1 * 8, pte(final_ppn, **perms))
            return
        self.write((root_ppn << 12) + vpn1 * 8, pte(mid_ppn, a=0, d=0))
        if level == 1:
            self.write((mid_ppn << 12) + vpn0 * 8, pte(final_ppn, **perms))
        else:
            self.write((mid_ppn << 12) + vpn0 * 8, pte(leaf_table_ppn, a=0, d=0))
            self.write((leaf_table_ppn << 12) + vpn_leaf * 8, pte(final_ppn, **perms))


@dataclass
class MemReq:
    source: int
    address: int
    size: int


class L2TlbEnv:
    def __init__(self, dut, coverage=None) -> None:
        self.dut = dut
        self.coverage = coverage
        self.memory = PageMemory()
        self.tick = 0
        self.requests: list[MemReq] = []
        self._pending_d: list[tuple[int, int, int, int, int]] = []
        self.mem_latency = 0
        self._monitor_enabled = False
        self._allow_new = True
        self.walk_script: dict[int, list[int]] | None = None
        self.walk_step: dict[int, int] = {}
        self.walk_ptes: dict[int, int] = {}
        self.leaf_word: int | None = None
        d = dut
        self.reset_pin = d.reset
        self.csr = dict(
            satp_mode=d.io_csr_tlb_satp_mode,
            satp_asid=d.io_csr_tlb_satp_asid,
            satp_ppn=d.io_csr_tlb_satp_ppn,
            satp_changed=d.io_csr_tlb_satp_changed,
            vsatp_mode=d.io_csr_tlb_vsatp_mode,
            vsatp_asid=d.io_csr_tlb_vsatp_asid,
            vsatp_ppn=d.io_csr_tlb_vsatp_ppn,
            vsatp_changed=d.io_csr_tlb_vsatp_changed,
            hgatp_mode=d.io_csr_tlb_hgatp_mode,
            hgatp_vmid=d.io_csr_tlb_hgatp_vmid,
            hgatp_ppn=d.io_csr_tlb_hgatp_ppn,
            hgatp_changed=d.io_csr_tlb_hgatp_changed,
            virt=d.io_csr_tlb_priv_virt,
            virt_changed=d.io_csr_tlb_priv_virt_changed,
            imode=d.io_csr_tlb_priv_imode,
            dmode=d.io_csr_tlb_priv_dmode,
            mxr=d.io_csr_tlb_priv_mxr,
            sum=d.io_csr_tlb_priv_sum,
            vmxr=d.io_csr_tlb_priv_vmxr,
            vsum=d.io_csr_tlb_priv_vsum,
            mPBMTE=d.io_csr_tlb_mPBMTE,
            hPBMTE=d.io_csr_tlb_hPBMTE,
            bme=d.io_csr_tlb_mbmc_BME,
            cmode=d.io_csr_tlb_mbmc_CMODE,
            bclear=d.io_csr_tlb_mbmc_BCLEAR,
            bma=d.io_csr_tlb_mbmc_BMA,
        )
        self.sfence = dict(
            valid=d.io_sfence_valid,
            rs1=d.io_sfence_bits_rs1,
            rs2=d.io_sfence_bits_rs2,
            addr=d.io_sfence_bits_addr,
            id=d.io_sfence_bits_id,
            hv=d.io_sfence_bits_hv,
            hg=d.io_sfence_bits_hg,
        )
        self.req = dict(
            ready=d.io_tlb_0_req_0_ready,
            valid=d.io_tlb_0_req_0_valid,
            vpn=d.io_tlb_0_req_0_bits_vpn,
            s2xlate=d.io_tlb_0_req_0_bits_s2xlate,
        )
        self.resp = dict(
            ready=d.io_tlb_0_resp_ready,
            valid=d.io_tlb_0_resp_valid,
            s2xlate=d.io_tlb_0_resp_bits_s2xlate,
            s1_tag=d.io_tlb_0_resp_bits_s1_entry_tag,
            s1_asid=d.io_tlb_0_resp_bits_s1_entry_asid,
            s1_level=d.io_tlb_0_resp_bits_s1_entry_level,
            s1_v=d.io_tlb_0_resp_bits_s1_entry_v,
            s1_ppn=d.io_tlb_0_resp_bits_s1_entry_ppn,
            s1_pf=d.io_tlb_0_resp_bits_s1_pf,
            s1_af=d.io_tlb_0_resp_bits_s1_af,
            s2_tag=d.io_tlb_0_resp_bits_s2_entry_tag,
            s2_ppn=d.io_tlb_0_resp_bits_s2_entry_ppn,
            s2_perm_a=d.io_tlb_0_resp_bits_s2_entry_perm_a,
            s2_perm_x=d.io_tlb_0_resp_bits_s2_entry_perm_x,
            s2_vmid=d.io_tlb_0_resp_bits_s2_entry_vmid,
            s2_level=d.io_tlb_0_resp_bits_s2_entry_level,
            s2_gpf=d.io_tlb_0_resp_bits_s2_gpf,
            s2_gaf=d.io_tlb_0_resp_bits_s2_gaf,
        )
        self.dist = dict(
            valid=d.io_csr_distribute_csr_w_valid,
            addr=d.io_csr_distribute_csr_w_bits_addr,
            data=d.io_csr_distribute_csr_w_bits_data,
        )
        self.req1 = dict(
            ready=d.io_tlb_1_req_0_ready,
            valid=d.io_tlb_1_req_0_valid,
            vpn=d.io_tlb_1_req_0_bits_vpn,
            s2xlate=d.io_tlb_1_req_0_bits_s2xlate,
        )
        self.resp1 = dict(
            valid=d.io_tlb_1_resp_valid,
            s2xlate=d.io_tlb_1_resp_bits_s2xlate,
            s1_tag=d.io_tlb_1_resp_bits_s1_entry_tag,
            s1_level=d.io_tlb_1_resp_bits_s1_entry_level,
            s1_v=d.io_tlb_1_resp_bits_s1_entry_v,
            s1_ppn=d.io_tlb_1_resp_bits_s1_entry_ppn,
            s1_pf=d.io_tlb_1_resp_bits_s1_pf,
            s1_af=d.io_tlb_1_resp_bits_s1_af,
        )
        self.a = dict(
            ready=d.auto_out_a_ready,
            valid=d.auto_out_a_valid,
            source=d.auto_out_a_bits_source,
            address=d.auto_out_a_bits_address,
        )
        self.d = dict(
            valid=d.auto_out_d_valid,
            opcode=d.auto_out_d_bits_opcode,
            size=d.auto_out_d_bits_size,
            source=d.auto_out_d_bits_source,
            data=d.auto_out_d_bits_data,
        )

    async def edge(self) -> None:
        self.dut.RefreshComb()
        if self._monitor_enabled and self.read(self.a["valid"]) and self.read(self.a["ready"]):
            self._accept_memory_request()
        await RisingEdge(self.dut.clock)
        self.tick += 1

    def _accept_memory_request(self) -> None:
        source = self.read(self.a["source"])
        address = self.read(self.a["address"])
        word = self._walk_word(source)
        base = address & ~0x3F
        if word is not None:
            lo = sum(word << (64 * shift) for shift in range(4))
            hi = lo
        else:
            lo = self.memory.read(base, 32)
            hi = self.memory.read(base + 32, 32)
        # The exported A interface has no size signal; this DUT always reads
        # a 64-byte cache line and exports two 256-bit D beats, without D.ready.
        self.requests.append(MemReq(source, address, 6))
        release = self.tick + max(1, self.mem_latency)
        self._pending_d.extend([(release, source, 1, 6, lo),
                                (release, source, 1, 6, hi)])

    def read(self, signal) -> int:
        return int(signal.value)

    def set_csr(self, **values) -> None:
        for key, value in values.items():
            self.csr[key].Set(value)
        self.dut.RefreshComb()

    async def write_csr(self, addr: int, data: int) -> None:
        self.dist["valid"].Set(1)
        self.dist["addr"].Set(addr)
        self.dist["data"].Set(data & ((1 << 64) - 1))
        await self.edge()
        self.dist["valid"].Set(0)
        self.dist["data"].Set(0)
        await self.edge()

    async def reset(self) -> None:
        self._monitor_enabled = False
        self._pending_d.clear()
        self.requests.clear()
        self.req["valid"].Set(0)
        self.resp["ready"].Set(0)
        self.set_csr(
            satp_mode=0, satp_asid=0, satp_ppn=0, satp_changed=0,
            vsatp_mode=0, vsatp_asid=0, vsatp_ppn=0, vsatp_changed=0,
            hgatp_mode=0, hgatp_vmid=0, hgatp_ppn=0, hgatp_changed=0,
            virt=0, virt_changed=0, imode=0, dmode=0, mxr=0, sum=0,
            vmxr=0, vsum=0, mPBMTE=0, hPBMTE=0,
            bme=0, cmode=0, bclear=0, bma=0,
        )
        for signal in self.sfence.values():
            signal.Set(0)
        self.d["valid"].Set(0)
        self.d["opcode"].Set(0)
        self.d["size"].Set(0)
        self.d["source"].Set(0)
        self.d["data"].Set(0)
        self.a["ready"].Set(1)
        self.dist["valid"].Set(0)
        self.dist["addr"].Set(0)
        self.dist["data"].Set(0)
        self.reset_pin.Set(1)
        await self.edge()
        await self.edge()
        self.reset_pin.Set(0)
        await self.edge()
        self._monitor_enabled = True

    def start_walk(self, final_ppn: int, perms: dict | None = None,
                   root_ppn: int = 0x80000, leaf_at_root: bool = False) -> None:
        perms = perms or dict(r=1, w=1, x=1, u=1, a=1, d=1)
        self.leaf_word = pte(final_ppn, **perms)
        if leaf_at_root:
            self.walk_script = {6: [pte(final_ppn, **perms)],
                                7: [pte(final_ppn, **perms)]}
            self.walk_step = {6: 0, 7: 0}
            return
        self.walk_script = {
            6: [pte(root_ppn + 1, a=0, d=0),
                pte(root_ppn + 2, a=0, d=0),
                pte(final_ppn, **perms)],
            7: [pte(root_ppn + 3, a=0, d=0),
                pte(root_ppn + 4, a=0, d=0),
                pte(final_ppn, **perms)],
        }
        self.walk_step = {6: 0, 7: 0}

    def _walk_word(self, source: int) -> int | None:
        if self.walk_script is None:
            return None
        if source not in self.walk_script:
            # LLPTW/prefetch requests for the same walk get a valid leaf so
            # they cannot poison the PtwCache line ahead of the PTW read.
            return self.leaf_word
        index = self.walk_step.get(source, 0)
        script = self.walk_script[source]
        self.walk_step[source] = index + 1
        if index < len(script):
            return script[index]
        return self.leaf_word

    async def service_memory(self, cycles: int, allow_new: bool = True) -> int:
        """Drive one D beat per cycle; always monitor every A fire."""
        before = len(self.requests)
        old_ready = self.read(self.a["ready"])
        if not allow_new:
            self.a["ready"].Set(0)
        for _ in range(cycles):
            self.d["valid"].Set(0)
            if self._pending_d and self._pending_d[0][0] <= self.tick:
                _, source, opcode, size, data = self._pending_d.pop(0)
                for key, value in (("valid", 1), ("opcode", opcode),
                                   ("size", size), ("source", source), ("data", data)):
                    self.d[key].Set(value)
            await self.edge()
            self.d["valid"].Set(0)
        if not allow_new:
            self.a["ready"].Set(old_ready)
        return len(self.requests) - before

    def _sample_response(self, snap: dict, port: int) -> None:
        stage = snap.get("s2xlate", 0)
        fault = False
        if stage == 2:
            fault = bool(snap.get("s2_gpf") or snap.get("s2_gaf"))
            level = snap.get("s2_level", 0)
        else:
            fault = (not snap.get("s1_v")) or bool(snap.get("s1_pf") or snap.get("s1_af"))
            if stage == 3:
                fault = fault or bool(snap.get("s2_gpf") or snap.get("s2_gaf"))
            level = snap.get("s1_level", 0)
        if fault:
            self.coverage.sample("fault", "fault", port, stage)
        else:
            page = {2: "1g", 1: "2m", 0: "4k"}.get(level, "4k")
            self.coverage.sample("walk", page, port, stage)

    async def issue(self, vpn: int, s2xlate: int = 0, port: int = 0) -> None:
        req = self.req if port == 0 else self.req1
        for _ in range(2000):
            self.dut.RefreshComb()
            if self.read(req["ready"]):
                break
            await self.service_memory(1)
        else:
            raise TimeoutError("L2TLB: input ready timeout")
        req["valid"].Set(1)
        req["vpn"].Set(vpn)
        req["s2xlate"].Set(s2xlate)
        await self.edge()
        req["valid"].Set(0)

    async def wait_response(self, max_cycles: int = 2000,
                            service: bool = True, note: str = "",
                            port: int = 0) -> dict:
        resp = self.resp if port == 0 else self.resp1
        if port == 0:
            self.resp["ready"].Set(1)
        for _ in range(max_cycles):
            if service:
                await self.service_memory(1)
            else:
                await self.edge()
            if self.read(resp["valid"]):
                snap = {key: self.read(signal) for key, signal in resp.items()}
                if self.coverage is not None:
                    self._sample_response(snap, port)
                if port == 0:
                    await self.edge()  # complete the ready/valid handshake
                return snap
        raise TimeoutError(f"{note}: no L2TLB response; memory requests={len(self.requests)}")
