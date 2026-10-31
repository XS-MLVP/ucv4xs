"""Timing-level environment for LoadPipe.

Calibrated transaction shape:

* request driven in cycle S0; tag/meta/bank-data read strobes are combinationally
  asserted for that cycle;
* tag/meta/bank-data responses must be stable in S1 (one cycle after S0);
* the public response fields (data/miss/mshr_id/handled) are valid in S2
  (two cycles after S0); there is no response-valid port.
"""
from __future__ import annotations

from .coverage import LoadPipeCoverage
from .model import block, dcache_index

FIELDS = ("cmd", "vaddr", "vaddr_dup", "mask", "instrtype", "lqidx")


class LoadPipeEnv:
    def __init__(self, dut, coverage: LoadPipeCoverage | None = None) -> None:
        self.dut = dut
        self.coverage = coverage
        self.req = {
            "valid": dut.io_lsu_req_valid,
            "cmd": dut.io_lsu_req_bits_cmd,
            "vaddr": dut.io_lsu_req_bits_vaddr,
            "vaddr_dup": dut.io_lsu_req_bits_vaddr_dup,
            "mask": dut.io_lsu_req_bits_mask,
            "instrtype": dut.io_lsu_req_bits_instrtype,
            "lqidx": dut.io_lsu_req_bits_lqIdx_value,
        }
        self.req_ready = dut.io_lsu_req_ready
        self.resp = {
            "data": dut.io_lsu_resp_bits_data,
            "miss": dut.io_lsu_resp_bits_miss,
            "mshr_id": dut.io_lsu_resp_bits_mshr_id,
            "handled": dut.io_lsu_resp_bits_handled,
            "meta_prefetch": dut.io_lsu_resp_bits_meta_prefetch,
        }
        self.tag = {
            "ready": dut.io_tag_read_ready,
            "valid": dut.io_tag_read_valid,
            "idx": dut.io_tag_read_bits_idx,
            "resp": [getattr(dut, f"io_tag_resp_{way}") for way in range(4)],
        }
        self.meta = {
            "valid": dut.io_meta_read_valid,
            "idx": dut.io_meta_read_bits_idx,
            "coh": [getattr(dut, f"io_meta_resp_{way}_coh_state") for way in range(4)],
        }
        self.bdata = {
            "ready": dut.io_banked_data_read_ready,
            "valid": dut.io_banked_data_read_valid,
            "way_en": dut.io_banked_data_read_bits_way_en,
            "addr": dut.io_banked_data_read_bits_addr,
            "bankMask": dut.io_banked_data_read_bits_bankMask,
            "lqidx": dut.io_banked_data_read_bits_lqIdx_value,
            "resp": [getattr(dut, f"io_banked_data_resp_{bank}_raw_data")
                     for bank in range(8)],
            "error": [getattr(dut, f"io_read_error_delayed_{bank}") for bank in range(8)],
        }
        self.miss = {
            "valid": dut.io_miss_req_valid,
            "ready": dut.io_miss_req_ready,
            "addr": dut.io_miss_req_bits_addr,
            "vaddr": dut.io_miss_req_bits_vaddr,
            "source": dut.io_miss_req_bits_source,
            "cmd": dut.io_miss_req_bits_cmd,
            "vaddrSet": dut.io_miss_req_bits_vaddrSet,
            "vaddrAlias": dut.io_miss_req_bits_vaddrAlias,
            "isSpecMiss": dut.io_miss_req_bits_isSpecMiss,
            "coh": dut.io_miss_req_bits_req_coh_state,
        }
        self.miss_resp = {
            "id": dut.io_miss_resp_id,
            "handled": dut.io_miss_resp_handled,
        }
        self.mshr_full = dut.io_mshr_full
        self.specmiss = {
            "valid": dut.io_specmiss_valid,
            "candidate": dut.io_specmiss_candidate,
            "grant_valid": dut.io_spec_query_grant_valid,
            "grant_bits": dut.io_spec_query_grant_bits,
        }
        self.load128 = dut.io_load128Req
        self.bank_conflict = dut.io_bank_conflict_slow
        self.rr_bank_conflict = dut.io_rr_bank_conflict_slow
        self.occupy_fail = dut.io_occupy_fail
        self.wbq_block = dut.io_wbq_block_miss_req
        self.s1_kill = dut.io_lsu_s1_kill
        self.s2_kill = dut.io_lsu_s2_kill
        self.paddr_dup_lsu = dut.io_lsu_s1_paddr_dup_lsu
        self.paddr_dup_dc = dut.io_lsu_s1_paddr_dup_dcache
        self.s2_bank_conflict = dut.io_lsu_s2_bank_conflict
        self.s2_rr_bank_conflict = dut.io_lsu_s2_rr_bank_conflict
        self.s2_mq_nack = dut.io_lsu_s2_mq_nack
        self.transactions = 0

    @staticmethod
    def _val(signal) -> int:
        return int(signal.value)

    def refresh(self) -> None:
        self.dut.xclock.RefreshComb()

    def _idle(self) -> None:
        self.req["valid"].Set(0)
        self.mshr_full.Set(0)
        self.specmiss["valid"].Set(0)
        self.specmiss["candidate"].Set(0)
        self.specmiss["grant_valid"].Set(0)
        self.load128.Set(0)
        self.bank_conflict.Set(0)
        self.rr_bank_conflict.Set(0)
        self.occupy_fail.Set(0)
        self.wbq_block.Set(0)
        self.s1_kill.Set(0)
        self.s2_kill.Set(0)

    def reset(self) -> None:
        self._idle()
        self.dut.reset.Set(1)
        self.dut.Step(3)
        self.dut.reset.Set(0)
        self.dut.Step(2)

    def _drive_responses(self, tag_way: int, tag_match: bool, paddr: int,
                         coh: int, banks: list[int]) -> None:
        tag = (paddr >> 12) & ((1 << 36) - 1)
        for way in range(4):
            self.tag["resp"][way].Set(tag if tag_match and way == tag_way
                                      else ((tag + 1) & ((1 << 36) - 1)))
            self.meta["coh"][way].Set(coh if tag_match and way == tag_way else 0)
        for bank in range(8):
            self.bdata["resp"][bank].Set(banks[bank])
        self.tag["ready"].Set(1)
        self.bdata["ready"].Set(1)

    def transaction(self, *, vaddr: int, paddr: int, mask: int = 0xFF,
                    cmd: int = 0, instrtype: int = 0, lqidx: int = 1,
                    tag_way: int = 0, tag_match: bool = True, coh: int = 3,
                    banks: list[int] | None = None,
                    mshr_full: bool = False, miss_handled: bool = True,
                    miss_id: int = 0, wbq_block: bool = False,
                    specmiss: bool = False, spec_grant: bool = False,
                    load128: bool = False, bank_conflict: bool = False,
                    rr_conflict: bool = False, occupy_fail: bool = False,
                    s1_kill: bool = False, s2_kill: bool = False,
                    context: str = "transaction") -> dict:
        banks = banks or [0x100 + bank for bank in range(8)]
        # The TLB duplicate physical address carries the same page offset as
        # the virtual address; keep the two consistent like the real LSU.
        paddr = (paddr & ~0xFFF) | (vaddr & 0xFFF)
        self._idle()
        self.req["valid"].Set(1)
        self.req["cmd"].Set(cmd)
        self.req["vaddr"].Set(vaddr)
        self.req["vaddr_dup"].Set(vaddr)
        self.req["mask"].Set(mask)
        self.req["instrtype"].Set(instrtype)
        self.req["lqidx"].Set(lqidx)
        self.paddr_dup_lsu.Set(paddr)
        self.paddr_dup_dc.Set(paddr)
        self.mshr_full.Set(1 if mshr_full else 0)
        self.specmiss["valid"].Set(1 if specmiss else 0)
        self.specmiss["candidate"].Set(1 if specmiss else 0)
        self.specmiss["grant_valid"].Set(1 if spec_grant else 0)
        self.specmiss["grant_bits"].Set(1 if spec_grant else 0)
        self.load128.Set(1 if load128 else 0)
        self.bank_conflict.Set(1 if bank_conflict else 0)
        self.rr_bank_conflict.Set(1 if rr_conflict else 0)
        self.occupy_fail.Set(1 if occupy_fail else 0)
        self.wbq_block.Set(1 if wbq_block else 0)
        self.miss["ready"].Set(1)
        self.miss_resp["id"].Set(miss_id)
        self.miss_resp["handled"].Set(1 if miss_handled else 0)
        self.s1_kill.Set(1 if s1_kill else 0)
        self.s2_kill.Set(1 if s2_kill else 0)
        self._drive_responses(tag_way, tag_match, paddr, coh, banks)
        self.refresh()
        s0 = {
            "req_ready": self._val(self.req_ready),
            "tag_valid": self._val(self.tag["valid"]),
            "tag_idx": self._val(self.tag["idx"]),
            "meta_valid": self._val(self.meta["valid"]),
            "meta_idx": self._val(self.meta["idx"]),
            "bdata_valid": self._val(self.bdata["valid"]),
            "bdata_way": self._val(self.bdata["way_en"]),
            "bdata_bank": self._val(self.bdata["bankMask"]),
        }
        self.dut.Step(1)
        self.req["valid"].Set(0)
        self.refresh()
        s1 = {
            "tag_valid": self._val(self.tag["valid"]),
            "bdata_way": self._val(self.bdata["way_en"]),
            "bdata_bank": self._val(self.bdata["bankMask"]),
        }
        self.dut.Step(1)
        self.refresh()
        s2 = {
            "data": self._val(self.resp["data"]),
            "miss": self._val(self.resp["miss"]),
            "mshr_id": self._val(self.resp["mshr_id"]),
            "handled": self._val(self.resp["handled"]),
            "miss_valid": self._val(self.miss["valid"]),
            "miss_addr": self._val(self.miss["addr"]),
            "miss_vaddr": self._val(self.miss["vaddr"]),
            "miss_isSpec": self._val(self.miss["isSpecMiss"]),
            "bank_conflict": self._val(self.s2_bank_conflict),
            "rr_conflict": self._val(self.s2_rr_bank_conflict),
        }
        self.transactions += 1
        expected_data = 0
        for bank in range(8):
            expected_data |= banks[bank] << (16 * bank)
        if s2["data"] != expected_data:
            raise AssertionError(
                f"{context}: data {s2['data']:#x} != {expected_data:#x}")
        if not s1_kill and s2["miss"] != (0 if tag_match else 1):
            raise AssertionError(
                f"{context}: miss={s2['miss']} for tag_match={tag_match}")
        if s0["tag_idx"] != dcache_index(vaddr) or s0["meta_idx"] != dcache_index(vaddr):
            raise AssertionError(
                f"{context}: tag/meta idx {s0['tag_idx']}/{s0['meta_idx']} != "
                f"{dcache_index(vaddr)}")
        if tag_match:
            if s0["bdata_way"] != (1 << tag_way):
                raise AssertionError(
                    f"{context}: bdata way {s0['bdata_way']:#x} != {1 << tag_way:#x}")
        want_miss_req = s2["miss_valid"]
        if want_miss_req:
            block_addr = paddr & ~0x3F
            if s2["miss_addr"] != block_addr or s2["miss_vaddr"] != vaddr:
                raise AssertionError(
                    f"{context}: miss addr/vaddr {s2['miss_addr']:#x}/"
                    f"{s2['miss_vaddr']:#x} != {block_addr:#x}/{vaddr:#x}")
        want_handled = int(want_miss_req and miss_handled and not wbq_block)
        if s2["handled"] != want_handled:
            raise AssertionError(
                f"{context}: handled {s2['handled']} != {want_handled}")
        if self.coverage is not None:
            self.coverage.sample(hit=tag_match, way=tag_way, cmd=cmd, mask=mask,
                                 load128=load128, mshr_full=mshr_full,
                                 specmiss=specmiss and spec_grant,
                                 handled=bool(want_handled),
                                 bank_conflict=bank_conflict,
                                 wbq_block=wbq_block)
        return {"s0": s0, "s1": s1, "s2": s2, "expected_data": expected_data}
