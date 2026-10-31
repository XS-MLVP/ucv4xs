"""Port-level environment and reference model for MainPipe.

Timing calibrated on the generated RTL (XiangShan kunminghu-v3 @ 893e1580):

* S0: the request is accepted; tag/meta read strobes are asserted with the
  DCache set index.  Tag/meta responses are sampled in S1 (one cycle later).
* S1: the banked data array read strobe is asserted when the operation needs
  line data; the 32 bank responses are sampled in S2.
* S2: miss requests towards the MissQueue are issued.  A store/atomic that
  must wait for the miss queue produces a replay response in this cycle.
* S3: tag/meta/data writes and the store/atomic/probe response are produced.

The environment drives the public ports only and keeps a byte-accurate model
of the 64B line, so a store merge, refill install and AMO result are checked
against the data that was read from the bank array.
"""
from __future__ import annotations

from .coverage import MainPipeCoverage
from ..duplicated_tag_array.model import codeword

BANKS = 32
WAYS = 4

M_XRD = 0
M_XWR = 1
M_PFR = 2
M_PFW = 3
M_XLR = 6
M_XSC = 7
M_XA_SWAP = 4
M_XA_ADD = 8
M_XA_CASQ = 0x18
M_XA_CASW = 0x1A
M_XA_CASD = 0x1B
M_XA_CASH = 0x1C
M_XA_CASB = 0x1D
CAS_CMDS = (M_XA_CASQ, M_XA_CASW, M_XA_CASD, M_XA_CASH, M_XA_CASB)

STORE_SOURCE = 1
PREFETCH_SOURCE = 3

# TileLink ClientStates / C-channel shrink encodings used by the RTL.
NOTHING, BRANCH, TRUNK, DIRTY = 0, 1, 2, 3
TTOB, TTON, BTON, TTOT, BTOB, NTON = 0, 1, 2, 3, 4, 5


def dcache_index(vaddr: int) -> int:
    hi = 0
    for bit in range(12, 48, 2):
        hi ^= (vaddr >> bit) & 0x3
    low = (vaddr >> 6) & 0x3F
    return ((hi & 0x3) << 6) | low


def phy_tag(paddr: int) -> int:
    return (paddr >> 12) & ((1 << 36) - 1)


def block_addr(paddr: int) -> int:
    return paddr & ~0x3F


def bank_mask_of_store(mask64: int) -> int:
    result = 0
    for bank in range(BANKS):
        if (mask64 >> (2 * bank)) & 0x3:
            result |= 1 << bank
    return result


def merge_line(old_banks: list[int], data: int, mask64: int) -> list[int]:
    """Merge a 64B store payload into a 64B line, bank by bank."""
    result = list(old_banks)
    for bank in range(BANKS):
        low_byte = (mask64 >> (2 * bank)) & 1
        high_byte = (mask64 >> (2 * bank + 1)) & 1
        if not (low_byte or high_byte):
            continue
        value = result[bank]
        if low_byte:
            value = (value & 0xFF00) | ((data >> (16 * bank)) & 0xFF)
        if high_byte:
            value = (value & 0x00FF) | (((data >> (16 * bank + 8)) & 0xFF) << 8)
        result[bank] = value
    return result


def line_from_banks(banks: list[int], first: int = 0, count: int = BANKS) -> int:
    value = 0
    for offset in range(count):
        value |= (banks[first + offset] & 0xFFFF) << (16 * offset)
    return value


def default_banks(base: int = 0x100) -> list[int]:
    return [(base + bank) & 0xFFFF for bank in range(BANKS)]


def first_cycle(snapshots: list[dict], key: str):
    for index, snap in enumerate(snapshots):
        if snap[key]:
            return index, snap
    return None, None


class MainPipeEnv:
    def __init__(self, dut, coverage: MainPipeCoverage | None = None) -> None:
        self.dut = dut
        self.coverage = coverage
        self.store = {
            "valid": dut.io_store_req_valid,
            "ready": dut.io_store_req_ready,
            "vaddr": dut.io_store_req_bits_vaddr,
            "addr": dut.io_store_req_bits_addr,
            "data": dut.io_store_req_bits_data,
            "mask": dut.io_store_req_bits_mask,
            "id": dut.io_store_req_bits_id,
            "hit_valid": dut.io_store_hit_resp_valid,
            "hit_id": dut.io_store_hit_resp_bits_id,
            "replay_valid": dut.io_store_replay_resp_valid,
            "replay_id": dut.io_store_replay_resp_bits_id,
        }
        self.atomic = {
            "valid": dut.io_atomic_req_valid,
            "ready": dut.io_atomic_req_ready,
            "cmd": dut.io_atomic_req_bits_cmd,
            "vaddr": dut.io_atomic_req_bits_vaddr,
            "addr": dut.io_atomic_req_bits_addr,
            "word_idx": dut.io_atomic_req_bits_word_idx,
            "data": dut.io_atomic_req_bits_amo_data,
            "mask": dut.io_atomic_req_bits_amo_mask,
            "cmp": dut.io_atomic_req_bits_amo_cmp,
            "resp_valid": dut.io_atomic_resp_valid,
            "resp_data": dut.io_atomic_resp_bits_data,
            "resp_source": dut.io_atomic_resp_bits_source,
            "resp_miss": dut.io_atomic_resp_bits_miss,
            "resp_miss_id": dut.io_atomic_resp_bits_miss_id,
            "resp_replay": dut.io_atomic_resp_bits_replay,
            "resp_denied": dut.io_atomic_resp_bits_tl_error_tl_denied,
            "resp_corrupt": dut.io_atomic_resp_bits_tl_error_tl_corrupt,
            "resp_ack_mq": dut.io_atomic_resp_bits_ack_miss_queue,
            "resp_id": dut.io_atomic_resp_bits_id,
        }
        self.probe = {
            "valid": dut.io_probe_req_valid,
            "ready": dut.io_probe_req_ready,
            "param": dut.io_probe_req_bits_probe_param,
            "need_data": dut.io_probe_req_bits_probe_need_data,
            "vaddr": dut.io_probe_req_bits_vaddr,
            "addr": dut.io_probe_req_bits_addr,
            "id": dut.io_probe_req_bits_id,
        }
        self.refill = {
            "valid": dut.io_refill_req_valid,
            "ready": dut.io_refill_req_ready,
            "miss_id": dut.io_refill_req_bits_miss_id,
            "occupy_way": dut.io_refill_req_bits_occupy_way,
            "evict_btot": dut.io_refill_req_bits_miss_fail_cause_evict_btot,
            "source": dut.io_refill_req_bits_source,
            "cmd": dut.io_refill_req_bits_cmd,
            "vaddr": dut.io_refill_req_bits_vaddr,
            "addr": dut.io_refill_req_bits_addr,
            "id": dut.io_refill_req_bits_id,
            "pf_source": dut.io_refill_req_bits_pf_source,
            "access": dut.io_refill_req_bits_access,
            "amo_data": dut.io_refill_req_bits_amo_data,
            "amo_mask": dut.io_refill_req_bits_amo_mask,
            "amo_cmp": dut.io_refill_req_bits_amo_cmp,
            "word_idx": dut.io_refill_req_bits_word_idx,
            "info_valid": dut.io_refill_info_valid,
            "info_data": dut.io_refill_info_bits_store_data,
            "info_mask": dut.io_refill_info_bits_store_mask,
            "info_param": dut.io_refill_info_bits_miss_param,
            "info_denied": dut.io_refill_info_bits_error_tl_denied,
            "info_corrupt": dut.io_refill_info_bits_error_tl_corrupt,
        }
        self.prefetch_req = {
            "valid": dut.io_prefetch_req_valid,
            "ready": dut.io_prefetch_req_ready,
            "paddr": dut.io_prefetch_req_bits_paddr,
            "vaddr": dut.io_prefetch_req_bits_vaddr,
            "source": dut.io_prefetch_req_bits_pf_source_value,
            "flag_valid": dut.io_prefetch_flag_write_valid,
            "flag_source": dut.io_prefetch_flag_write_bits_source,
            "access_valid": dut.io_access_flag_write_valid,
            "access_flag": dut.io_access_flag_write_bits_flag,
            "access_way": dut.io_access_flag_write_bits_way_en,
        }
        self.miss = {
            "valid": dut.io_miss_req_valid,
            "ready": dut.io_miss_req_ready,
            "source": dut.io_miss_req_bits_source,
            "pf_source": dut.io_miss_req_bits_pf_source,
            "cmd": dut.io_miss_req_bits_cmd,
            "addr": dut.io_miss_req_bits_addr,
            "vaddr": dut.io_miss_req_bits_vaddr,
            "store_data": dut.io_miss_req_bits_store_data,
            "store_mask": dut.io_miss_req_bits_store_mask,
            "amo_data": dut.io_miss_req_bits_amo_data,
            "amo_mask": dut.io_miss_req_bits_amo_mask,
            "amo_cmp": dut.io_miss_req_bits_amo_cmp,
            "word_idx": dut.io_miss_req_bits_word_idx,
            "vaddr_alias": dut.io_miss_req_bits_vaddrAlias,
            "vaddr_set": dut.io_miss_req_bits_vaddrSet,
            "req_coh": dut.io_miss_req_bits_req_coh_state,
            "id": dut.io_miss_req_bits_id,
            "full_overwrite": dut.io_miss_req_bits_full_overwrite,
            "occupy_way": dut.io_miss_req_bits_occupy_way,
            "isBtoT": dut.io_miss_req_bits_isBtoT,
            "cancel": dut.io_miss_req_bits_cancel,
        }
        self.wb = {
            "valid": dut.io_wb_valid,
            "ready": dut.io_wb_ready,
            "param": dut.io_wb_bits_param,
            "voluntary": dut.io_wb_bits_voluntary,
            "hasData": dut.io_wb_bits_hasData,
            "corrupt": dut.io_wb_bits_corrupt,
            "addr": dut.io_wb_bits_addr,
            "data": dut.io_wb_bits_data,
        }
        self.tag = {
            "read_ready": dut.io_tag_read_ready,
            "read_valid": dut.io_tag_read_valid,
            "read_idx": dut.io_tag_read_bits_idx,
            "resp": [getattr(dut, f"io_tag_resp_{way}") for way in range(WAYS)],
            "write_valid": dut.io_tag_write_valid,
            "write_idx": dut.io_tag_write_bits_idx,
            "write_way": dut.io_tag_write_bits_way_en,
            "write_tag": dut.io_tag_write_bits_tag,
            "write_intend": dut.io_tag_write_intend,
        }
        self.meta = {
            "read_valid": dut.io_meta_read_valid,
            "read_idx": dut.io_meta_read_bits_idx,
            "resp": [getattr(dut, f"io_meta_resp_{way}_coh_state") for way in range(WAYS)],
            "write_valid": dut.io_meta_write_valid,
            "write_idx": dut.io_meta_write_bits_idx,
            "write_way": dut.io_meta_write_bits_way_en,
            "write_coh": dut.io_meta_write_bits_meta_coh_state,
        }
        self.data = {
            "readline_ready": dut.io_data_readline_ready,
            "readline_valid": dut.io_data_readline_valid,
            "readline_way": dut.io_data_readline_bits_way_en,
            "readline_addr": dut.io_data_readline_bits_addr,
            "readline_rmask": dut.io_data_readline_bits_rmask,
            "readline_can_go": dut.io_data_readline_can_go,
            "readline_can_resp": dut.io_data_readline_can_resp,
            "resp": [getattr(dut, f"io_data_resp_{bank}_raw_data") for bank in range(BANKS)],
            "write_valid": dut.io_data_write_valid,
            "write_wmask": dut.io_data_write_bits_wmask,
            "write_data": [getattr(dut, f"io_data_write_bits_data_{bank}")
                           for bank in range(BANKS)],
        }
        self.error_flag = {
            "valid": dut.io_error_flag_write_valid,
            "idx": dut.io_error_flag_write_bits_idx,
            "way": dut.io_error_flag_write_bits_way_en,
            "denied": dut.io_error_flag_write_bits_error_tl_denied,
            "corrupt": dut.io_error_flag_write_bits_error_tl_corrupt,
        }
        self.error = {
            "valid": dut.io_error_valid,
            "paddr": dut.io_error_bits_paddr,
            "report": dut.io_error_bits_report_to_beu,
        }
        self.replace = {
            "access_valid": dut.io_replace_access_valid,
            "access_set": dut.io_replace_access_bits_set,
            "access_way": dut.io_replace_access_bits_way,
            "way_set_bits": dut.io_replace_way_set_bits,
            "way_way": dut.io_replace_way_way,
        }
        self.info = {
            "s2_valid": dut.io_mainpipe_info_s2_valid,
            "s2_miss_id": dut.io_mainpipe_info_s2_miss_id,
            "s3_valid": dut.io_mainpipe_info_s3_valid,
            "s3_refill_resp": dut.io_mainpipe_info_s3_refill_resp,
            "s3_miss_id": dut.io_mainpipe_info_s3_miss_id,
            "s2_next_evict_way": dut.io_mainpipe_info_s2_next_evict_way,
            "s2_evict_btot": dut.io_mainpipe_info_s2_evict_BtoT_way,
        }
        self.extra = {
            "pseudo_valid": dut.io_pseudo_error_valid,
            "pseudo_0_valid": dut.io_pseudo_error_bits_0_valid,
            "pseudo_0_mask": dut.io_pseudo_error_bits_0_mask,
            "pseudo_tag_done": dut.io_pseudo_tag_error_inj_done,
            "pseudo_data_done": dut.io_pseudo_data_error_inj_done,
            "readline_error": dut.io_readline_error_delayed,
            "btot_ways": dut.io_btot_ways_for_set,
            "invalid_resv": dut.io_invalid_resv_set,
            "lrsc_valid": dut.io_lrsc_locked_block_valid,
            "lrsc_block": dut.io_lrsc_locked_block_bits,
            "block_lr": dut.io_block_lr,
            "misstrack_valid": dut.io_misstrack_install_valid,
            "misstrack_vaddr": dut.io_misstrack_install_bits_vaddr,
            "misstrack_paddr": dut.io_misstrack_install_bits_paddr,
            "misstrack_way": dut.io_misstrack_install_bits_way,
            "wbq_block": dut.io_wbq_block_miss_req,
            "wbq_conflict_valid": dut.io_wbq_conflict_check_valid,
            "extra_error": [
                {
                    "denied": getattr(dut, f"io_extra_meta_resp_{way}_error_tl_denied"),
                    "corrupt": getattr(dut, f"io_extra_meta_resp_{way}_error_tl_corrupt"),
                } for way in range(WAYS)
            ],
        }
        self.index = dcache_index
        self.phy_tag = phy_tag
        self.transactions = 0

    @staticmethod
    def _val(signal) -> int:
        return int(signal.value)

    def refresh(self) -> None:
        self.dut.xclock.RefreshComb()

    def _idle(self) -> None:
        for req in (self.store, self.atomic, self.probe, self.refill, self.prefetch_req):
            req["valid"].Set(0)
        self.refill["info_valid"].Set(0)
        self.refill["info_denied"].Set(0)
        self.refill["info_corrupt"].Set(0)
        self.extra["readline_error"].Set(0)
        self.extra["invalid_resv"].Set(0)
        self.extra["wbq_block"].Set(0)
        for way in range(WAYS):
            self.extra["extra_error"][way]["denied"].Set(0)
            self.extra["extra_error"][way]["corrupt"].Set(0)

    def reset(self) -> None:
        self._idle()
        for way in range(WAYS):
            self.tag["resp"][way].Set(0)
            self.meta["resp"][way].Set(0)
        for bank in range(BANKS):
            self.data["resp"][bank].Set(0)
        self.tag["read_ready"].Set(1)
        self.data["readline_ready"].Set(1)
        self.miss["ready"].Set(1)
        self.wb["ready"].Set(1)
        self.replace["way_way"].Set(0)
        self.extra["btot_ways"].Set(0)
        self.dut.reset.Set(1)
        self.dut.Step(4)
        self.dut.reset.Set(0)
        self.dut.Step(2)

    def drive_line(self, paddr: int, banks: list[int], *, hit_way: int = 0,
                   coh: int = 3, tag_match: bool = True,
                   replace_way: int = 0, replace_coh: int | None = None,
                   extra_error: tuple[int, str] | None = None,
                   readline_error: bool = False,
                   tag_ecc_bad: bool = False) -> None:
        tag = codeword(phy_tag(paddr))
        if tag_ecc_bad:
            tag ^= 0x1
        other = codeword(0x12345678)
        for way in range(WAYS):
            self.tag["resp"][way].Set(tag if (tag_match and way == hit_way) else other)
            self.meta["resp"][way].Set(coh if (tag_match and way == hit_way) else 0)
        if not tag_match and replace_coh is not None:
            self.meta["resp"][replace_way].Set(replace_coh)
        for bank in range(BANKS):
            self.data["resp"][bank].Set(banks[bank] & 0xFFFF)
        self.replace["way_way"].Set(replace_way)
        self.extra["readline_error"].Set(1 if readline_error else 0)
        for way in range(WAYS):
            for kind in ("denied", "corrupt"):
                self.extra["extra_error"][way][kind].Set(0)
        if extra_error is not None:
            way, kind = extra_error
            self.extra["extra_error"][way][kind].Set(1)

    def take_snapshot(self) -> dict:
        v = self._val
        return {
            "tag_read": v(self.tag["read_valid"]),
            "tag_read_idx": v(self.tag["read_idx"]),
            "meta_read": v(self.meta["read_valid"]),
            "meta_read_idx": v(self.meta["read_idx"]),
            "readline": v(self.data["readline_valid"]),
            "readline_way": v(self.data["readline_way"]),
            "readline_rmask": v(self.data["readline_rmask"]),
            "miss_req": v(self.miss["valid"]),
            "miss_ready": v(self.miss["ready"]),
            "miss_addr": v(self.miss["addr"]),
            "miss_vaddr": v(self.miss["vaddr"]),
            "miss_source": v(self.miss["source"]),
            "miss_pf_source": v(self.miss["pf_source"]),
            "miss_cmd": v(self.miss["cmd"]),
            "miss_store_data": v(self.miss["store_data"]),
            "miss_store_mask": v(self.miss["store_mask"]),
            "miss_amo_data": v(self.miss["amo_data"]),
            "miss_amo_mask": v(self.miss["amo_mask"]),
            "miss_amo_cmp": v(self.miss["amo_cmp"]),
            "miss_word_idx": v(self.miss["word_idx"]),
            "miss_vaddr_alias": v(self.miss["vaddr_alias"]),
            "miss_vaddr_set": v(self.miss["vaddr_set"]),
            "miss_req_coh": v(self.miss["req_coh"]),
            "miss_id": v(self.miss["id"]),
            "miss_full_overwrite": v(self.miss["full_overwrite"]),
            "miss_occupy_way": v(self.miss["occupy_way"]),
            "miss_isBtoT": v(self.miss["isBtoT"]),
            "miss_cancel": v(self.miss["cancel"]),
            "store_ready": v(self.store["ready"]),
            "store_hit": v(self.store["hit_valid"]),
            "store_hit_id": v(self.store["hit_id"]),
            "store_replay": v(self.store["replay_valid"]),
            "store_replay_id": v(self.store["replay_id"]),
            "atomic_resp": v(self.atomic["resp_valid"]),
            "atomic_data": v(self.atomic["resp_data"]),
            "atomic_miss": v(self.atomic["resp_miss"]),
            "atomic_miss_id": v(self.atomic["resp_miss_id"]),
            "atomic_replay": v(self.atomic["resp_replay"]),
            "atomic_ack_mq": v(self.atomic["resp_ack_mq"]),
            "atomic_denied": v(self.atomic["resp_denied"]),
            "atomic_corrupt": v(self.atomic["resp_corrupt"]),
            "atomic_id": v(self.atomic["resp_id"]),
            "tag_write": v(self.tag["write_valid"]),
            "tag_write_idx": v(self.tag["write_idx"]),
            "tag_write_way": v(self.tag["write_way"]),
            "tag_write_tag": v(self.tag["write_tag"]),
            "meta_write": v(self.meta["write_valid"]),
            "meta_write_idx": v(self.meta["write_idx"]),
            "meta_write_way": v(self.meta["write_way"]),
            "meta_write_coh": v(self.meta["write_coh"]),
            "data_write": v(self.data["write_valid"]),
            "data_wmask": v(self.data["write_wmask"]),
            "data_values": [v(signal) for signal in self.data["write_data"]],
            "wb": v(self.wb["valid"]),
            "wb_param": v(self.wb["param"]),
            "wb_voluntary": v(self.wb["voluntary"]),
            "wb_hasdata": v(self.wb["hasData"]),
            "wb_corrupt": v(self.wb["corrupt"]),
            "wb_addr": v(self.wb["addr"]),
            "wb_data": v(self.wb["data"]),
            "error_flag": v(self.error_flag["valid"]),
            "error_flag_idx": v(self.error_flag["idx"]),
            "error_flag_way": v(self.error_flag["way"]),
            "error_flag_denied": v(self.error_flag["denied"]),
            "error_flag_corrupt": v(self.error_flag["corrupt"]),
            "error_valid": v(self.error["valid"]),
            "error_paddr": v(self.error["paddr"]),
            "error_report": v(self.error["report"]),
            "s3_refill_resp": v(self.info["s3_refill_resp"]),
            "s3_miss_id": v(self.info["s3_miss_id"]),
            "s2_next_evict_way": v(self.info["s2_next_evict_way"]),
            "s2_evict_btot": v(self.info["s2_evict_btot"]),
            "replace_access": v(self.replace["access_valid"]),
            "replace_access_set": v(self.replace["access_set"]),
            "replace_access_way": v(self.replace["access_way"]),
            "lrsc_valid": v(self.extra["lrsc_valid"]),
            "lrsc_block": v(self.extra["lrsc_block"]),
            "block_lr": v(self.extra["block_lr"]),
            "misstrack_valid": v(self.extra["misstrack_valid"]),
            "misstrack_way": v(self.extra["misstrack_way"]),
            "btot_ways": v(self.extra["btot_ways"]),
            "prefetch_flag": v(self.prefetch_req["flag_valid"]),
            "prefetch_flag_source": v(self.prefetch_req["flag_source"]),
            "access_flag": v(self.prefetch_req["access_valid"]),
            "access_flag_value": v(self.prefetch_req["access_flag"]),
            "access_flag_way": v(self.prefetch_req["access_way"]),
            "tag_write_intend": v(self.tag["write_intend"]),
        }

    def run(self, *, cycles: int = 8, hold: int = 1) -> list[dict]:
        """Step the DUT, dropping only the request valid after `hold` cycles.

        Tag/meta/bank responses and the refill payload stay asserted for the
        whole window because S1/S2 sample them one/two cycles after the fire.
        """
        snapshots = []
        for cycle in range(cycles):
            if cycle == hold:
                for req in (self.store, self.atomic, self.probe, self.refill,
                            self.prefetch_req):
                    req["valid"].Set(0)
            self.refresh()
            self.dut.Step(1)
            snapshots.append(self.take_snapshot())
        self.transactions += 1
        return snapshots

    # ------------------------------------------------------------------ store
    def store_op(self, *, vaddr: int, paddr: int, data: int, mask: int = 0xFF,
                 store_id: int = 0, banks: list[int] | None = None,
                 coh: int = DIRTY, hit_way: int = 0, tag_match: bool = True,
                 miss_ready: bool = True, replace_way: int = 0,
                 replace_coh: int | None = None, btot: int = 0,
                 readline_error: bool = False, hold: int = 1,
                 cycles: int = 6) -> dict:
        banks = banks or default_banks()
        self._idle()
        self.store["valid"].Set(1)
        self.store["vaddr"].Set(vaddr)
        self.store["addr"].Set(paddr)
        self.store["data"].Set(data)
        self.store["mask"].Set(mask)
        self.store["id"].Set(store_id)
        self.miss["ready"].Set(1 if miss_ready else 0)
        self.extra["btot_ways"].Set(btot)
        self.drive_line(paddr, banks, hit_way=hit_way, coh=coh,
                        tag_match=tag_match, replace_way=replace_way,
                        replace_coh=replace_coh,
                        readline_error=readline_error)
        self.refresh()
        s0 = self.take_snapshot()
        snaps = self.run(cycles=cycles, hold=hold)
        hit = any(snap["store_hit"] for snap in snaps)
        replay = any(snap["store_replay"] for snap in snaps)
        miss = any(snap["miss_req"] for snap in snaps)
        # A store that enters the MSHR also produces store_hit_resp (with the
        # miss flag folded into the response), so the miss request wins.
        if replay:
            outcome = "replay"
        elif miss:
            outcome = "miss_accepted"
        elif hit:
            outcome = "hit"
        else:
            outcome = "none"
        meta_update = "to_dirty" if any(
            snap["meta_write"] and snap["meta_write_coh"] == DIRTY for snap in snaps
        ) else "none"
        index = dcache_index(vaddr)
        if self.coverage is not None:
            self.coverage.sample_store(outcome, mask, meta_update, index, hit_way)
        return {
            "snapshots": snaps,
            "s0": s0,
            "all": [s0, *snaps],
            "outcome": outcome,
            "banks": banks,
            "index": index,
            "expected_wmask": bank_mask_of_store(mask),
            "expected_line": merge_line(banks, data, mask),
        }

    # ----------------------------------------------------------------- atomic
    def atomic_op(self, *, vaddr: int, paddr: int, cmd: int, amo_data: int = 0,
                  amo_mask: int = 0xFF, amo_cmp: int = 0, word_idx: int = 0,
                  banks: list[int] | None = None, coh: int = DIRTY,
                  hit_way: int = 0, tag_match: bool = True,
                  miss_ready: bool = True, replace_way: int = 0,
                  replace_coh: int | None = None, invalid_resv: bool = False,
                  readline_error: bool = False, tag_ecc_bad: bool = False,
                  reservation: str = "valid", cycles: int = 6) -> dict:
        banks = banks or default_banks()
        self._idle()
        self.atomic["valid"].Set(1)
        self.atomic["cmd"].Set(cmd)
        self.atomic["vaddr"].Set(vaddr)
        self.atomic["addr"].Set(paddr)
        self.atomic["word_idx"].Set(word_idx)
        self.atomic["data"].Set(amo_data)
        self.atomic["mask"].Set(amo_mask)
        self.atomic["cmp"].Set(amo_cmp)
        self.miss["ready"].Set(1 if miss_ready else 0)
        self.drive_line(paddr, banks, hit_way=hit_way, coh=coh,
                        tag_match=tag_match, replace_way=replace_way,
                        replace_coh=replace_coh,
                        readline_error=readline_error)
        self.refresh()
        s0 = self.take_snapshot()
        snaps = self.run(cycles=cycles)
        hit = any(snap["atomic_resp"] and not snap["atomic_miss"] for snap in snaps)
        miss = any(snap["miss_req"] for snap in snaps)
        replay = any(snap["atomic_replay"] for snap in snaps)
        if hit:
            outcome = "hit"
        elif replay:
            outcome = "miss_replay"
        elif miss:
            outcome = "miss"
        else:
            outcome = "none"
        if cmd == M_XA_CASQ:
            word_base = (word_idx >> 1) * 8
        else:
            word_base = word_idx * 4
        old_word = line_from_banks(banks, word_base, 4)
        if cmd == M_XA_SWAP:
            result_word = amo_data & 0xFFFFFFFFFFFFFFFF
        elif cmd in CAS_CMDS:
            # Compare-then-write: only a matching compare updates the line.
            if self._cas_match(banks, word_base, amo_cmp, cmd):
                result_word = amo_data & 0xFFFFFFFFFFFFFFFF
            else:
                result_word = old_word
        elif cmd == M_XA_ADD:
            result_word = (old_word + (amo_data & 0xFFFFFFFFFFFFFFFF)) & 0xFFFFFFFFFFFFFFFF
        else:
            result_word = old_word
        expected_word = line_from_banks(banks, word_base, 4)
        for byte in range(8):
            if (amo_mask >> byte) & 1:
                shift = 8 * byte
                expected_word = ((expected_word & ~(0xFF << shift))
                                 | (((result_word >> shift) & 0xFF) << shift))
        if self.coverage is not None:
            if cmd in (M_XLR, M_XSC):
                self.coverage.sample_lrsc(
                    "lr" if cmd == M_XLR else "sc", reservation,
                    any(snap["data_write"] for snap in snaps))
            elif cmd in CAS_CMDS:
                self.coverage.sample_cas(cmd, self._cas_match(banks, word_base,
                                                             amo_cmp, cmd),
                                         outcome)
            else:
                op = "swap" if cmd == M_XA_SWAP else "add"
                self.coverage.sample_atomic(op, outcome, amo_mask)
        return {
            "snapshots": snaps,
            "s0": s0,
            "all": [s0, *snaps],
            "outcome": outcome,
            "word_base": word_base,
            "old_word": old_word,
            "expected_word": expected_word,
            "expected_resp": line_from_banks(banks, word_base, 8),
            "cas_match": self._cas_match(banks, word_base, amo_cmp, cmd)
            if cmd in CAS_CMDS else None,
            "expected_wmask": 0xF << word_base,
        }

    def clear_reservation(self, cycles: int = 2) -> list[dict]:
        self._idle()
        self.extra["invalid_resv"].Set(1)
        self.refresh()
        self.dut.Step(1)
        self.refresh()
        self.extra["invalid_resv"].Set(0)
        snaps = []
        for _ in range(cycles):
            self.refresh()
            self.dut.Step(1)
            snaps.append(self.take_snapshot())
        self.refresh()
        return snaps

    @staticmethod
    def _cas_match(banks: list[int], word_base: int, amo_cmp: int,
                   cmd: int) -> bool:
        if cmd == M_XA_CASQ:
            width = 16
        elif cmd == M_XA_CASD:
            width = 8
        elif cmd == M_XA_CASW:
            width = 4
        elif cmd == M_XA_CASH:
            width = 2
        else:
            width = 1
        old = line_from_banks(banks, word_base, (width + 1) // 2)
        mask = (1 << (8 * width)) - 1
        return (old & mask) == (amo_cmp & mask)

    # ------------------------------------------------------------------ probe
    def probe_op(self, *, vaddr: int, paddr: int, param: int = 0,
                 need_data: bool = False, probe_id: int = 0,
                 banks: list[int] | None = None, coh: int = DIRTY,
                 hit_way: int = 0, tag_match: bool = True,
                 replace_way: int = 0, extra_error: tuple[int, str] | None = None,
                 readline_error: bool = False, tag_ecc_bad: bool = False,
                 stall_readline_at: int | None = None,
                 cycles: int = 6) -> dict:
        banks = banks or default_banks()
        self._idle()
        self.probe["valid"].Set(1)
        self.probe["param"].Set(param)
        self.probe["need_data"].Set(1 if need_data else 0)
        self.probe["vaddr"].Set(vaddr)
        self.probe["addr"].Set(paddr)
        self.probe["id"].Set(probe_id)
        self.drive_line(paddr, banks, hit_way=hit_way, coh=coh,
                        tag_match=tag_match, replace_way=replace_way,
                        extra_error=extra_error,
                        readline_error=readline_error,
                        tag_ecc_bad=tag_ecc_bad)
        self.refresh()
        s0 = self.take_snapshot()
        if stall_readline_at is None:
            snaps = self.run(cycles=cycles)
        else:
            # Stall S1 for one cycle so the next S2 capture uses the registered
            # extra-meta error bits instead of the live tag/meta response.
            snaps = []
            for cycle in range(cycles):
                if cycle == 1:
                    for req in (self.store, self.atomic, self.probe, self.refill,
                                self.prefetch_req):
                        req["valid"].Set(0)
                if cycle == stall_readline_at:
                    self.data["readline_ready"].Set(0)
                self.refresh()
                self.dut.Step(1)
                snaps.append(self.take_snapshot())
                if cycle == stall_readline_at:
                    self.data["readline_ready"].Set(1)
            self.transactions += 1
        wb_cycle, wb = first_cycle(snaps, "wb")
        meta_cycle, meta = first_cycle(snaps, "meta_write")
        new_coh = {TTOT: TRUNK, TTOB: BRANCH, TTON: NOTHING, BTOB: BRANCH,
                   NTON: NOTHING}.get(wb["wb_param"] if wb else -1, "unknown")
        if self.coverage is not None:
            self.coverage.sample_probe(
                param, {TRUNK: "trunk", BRANCH: "branch", NOTHING: "nothing"}.get(
                    new_coh if meta else coh, "nothing"),
                bool(wb and wb["wb_hasdata"]), tag_match)
            if tag_ecc_bad:
                self.coverage.sample_ecc("tag")
            if readline_error:
                self.coverage.sample_ecc("data")
            if extra_error is not None:
                self.coverage.sample_flag_error(extra_error[1])
        return {
            "snapshots": snaps,
            "s0": s0,
            "all": [s0, *snaps],
            "wb_cycle": wb_cycle,
            "wb": wb,
            "meta_cycle": meta_cycle,
            "meta": meta,
            "new_coh": new_coh,
            "banks": banks,
        }

    # ----------------------------------------------------------------- refill
    def refill_op(self, *, vaddr: int, paddr: int, cmd: int = M_XRD,
                  miss_id: int = 0, source: int = 2, occupy_way: int = 0,
                  line_data: int | None = None, miss_param: int = 0,
                  miss_dirty: bool = False, denied: bool = False,
                  corrupt: bool = False, pf_source: int = 0, access: bool = True,
                  amo_data: int = 0, amo_mask: int = 0, amo_cmp: int = 0,
                  word_idx: int = 0, evict_btot: bool = False,
                  banks: list[int] | None = None, coh: int = NOTHING,
                  tag_match: bool = False, hit_way: int = 0,
                  replace_way: int = 0, replace_coh: int | None = None,
                  cycles: int = 6) -> dict:
        banks = banks or default_banks(0x100)
        if line_data is None:
            line_data = line_from_banks([(0x5A00 + bank) & 0xFFFF for bank in range(BANKS)])
        self._idle()
        self.refill["valid"].Set(1)
        self.refill["miss_id"].Set(miss_id)
        self.refill["occupy_way"].Set(occupy_way)
        self.refill["evict_btot"].Set(1 if evict_btot else 0)
        self.refill["source"].Set(source)
        self.refill["cmd"].Set(cmd)
        self.refill["vaddr"].Set(vaddr)
        self.refill["addr"].Set(paddr)
        self.refill["id"].Set(0)
        self.refill["pf_source"].Set(pf_source)
        self.refill["access"].Set(1 if access else 0)
        self.refill["amo_data"].Set(amo_data)
        self.refill["amo_mask"].Set(amo_mask)
        self.refill["amo_cmp"].Set(amo_cmp)
        self.refill["word_idx"].Set(word_idx)
        self.refill["info_valid"].Set(1)
        self.refill["info_data"].Set(line_data)
        self.refill["info_mask"].Set((1 << 64) - 1)
        self.refill["info_param"].Set(miss_param)
        self.refill["info_denied"].Set(1 if denied else 0)
        self.refill["info_corrupt"].Set(1 if corrupt else 0)
        self.drive_line(paddr, banks, hit_way=hit_way, coh=coh,
                        tag_match=tag_match, replace_way=replace_way,
                        replace_coh=replace_coh)
        self.refresh()
        s0 = self.take_snapshot()
        snaps = self.run(cycles=cycles)
        error = "denied" if denied else "corrupt" if corrupt else "clean"
        if cmd == M_XWR:
            kind = "store"
        elif cmd in (M_XA_SWAP, M_XA_ADD):
            kind = "amo"
        else:
            kind = "load"
        new_coh = TRUNK if kind == "load" else DIRTY
        index = dcache_index(vaddr)
        if self.coverage is not None:
            self.coverage.sample_refill(kind, replace_way, error, index)
            if replace_coh is not None:
                self.coverage.sample_eviction(replace_coh, tag_match)
        return {
            "snapshots": snaps,
            "s0": s0,
            "all": [s0, *snaps],
            "index": index,
            "expected_tag": phy_tag(paddr),
            "expected_way": occupy_way if evict_btot else 1 << replace_way,
            "expected_data": [((line_data >> (16 * bank)) & 0xFFFF)
                              for bank in range(BANKS)],
            "new_coh": new_coh,
            "kind": kind,
            "error": error,
        }

    # --------------------------------------------------------------- prefetch
    def prefetch_op(self, *, vaddr: int, paddr: int, source: int = 5,
                    banks: list[int] | None = None, coh: int = DIRTY,
                    hit_way: int = 0, tag_match: bool = True,
                    miss_ready: bool = True, replace_way: int = 0,
                    cycles: int = 6) -> dict:
        banks = banks or default_banks()
        self._idle()
        self.prefetch_req["valid"].Set(1)
        self.prefetch_req["paddr"].Set(paddr)
        self.prefetch_req["vaddr"].Set(vaddr)
        self.prefetch_req["source"].Set(source)
        self.miss["ready"].Set(1 if miss_ready else 0)
        self.drive_line(paddr, banks, hit_way=hit_way, coh=coh,
                        tag_match=tag_match, replace_way=replace_way)
        self.refresh()
        s0 = self.take_snapshot()
        snaps = self.run(cycles=cycles)
        miss_cycle, miss = first_cycle(snaps, "miss_req")
        if self.coverage is not None:
            self.coverage.sample_prefetch(tag_match, source)
        return {
            "snapshots": snaps,
            "s0": s0,
            "all": [s0, *snaps],
            "miss_cycle": miss_cycle,
            "miss": miss,
            "banks": banks,
        }
