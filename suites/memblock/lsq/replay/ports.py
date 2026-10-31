"""Observe all actual public pins; independently decode the driven transactions."""
import json

from suites.memblock.lsq.native import ROOT
from suites.memblock.lsq.raw.types import FtqPtr, SqPtr
from suites.memblock.lsq.vlq.types import QueuePtr, Redirect, RobPtr
from .codec import encode
from .types import Enqueue, Inputs, L2Hint, LqWakeup, Refill, StoreWakeup, TlbHint, Uop, SOURCE_EXCEPTION_BITS


def decode(values):
    def rob(prefix):
        return RobPtr(bool(values[prefix + "flag"]), values[prefix + "value"], bool(values[prefix + "isFormer"]))
    def sq(prefix):
        return SqPtr(bool(values[prefix + "first_flag"]), bool(values[prefix + "second_flag"]), values[prefix + "value"])
    def lq(prefix):
        return QueuePtr(bool(values[prefix + "flag"]), values[prefix + "value"])
    enqueues = []
    for lane in range(3):
        prefix = f"io_enq_{lane}_"
        get = lambda suffix: values[prefix + suffix]
        uop = Uop(rob=rob(prefix + "bits_uop_robIdx_"), lq=lq(prefix + "bits_uop_lqIdx_"), sq=sq(prefix + "bits_uop_sqIdx_"),
                  ftq=FtqPtr(bool(get("bits_uop_ftqPtr_flag")), get("bits_uop_ftqPtr_value")), offset=get("bits_uop_ftqOffset"),
                  rvc=bool(get("bits_uop_isRVC")), checkpoint=get("bits_uop_perfDebugInfo_runahead_checkpoint_id"),
                  operation=get("bits_uop_fuOpType"), integer_write=bool(get("bits_uop_rfWen")), fp_write=bool(get("bits_uop_fpWen")),
                  vector_write=bool(get("bits_uop_vecWen")), v0_write=bool(get("bits_uop_v0Wen")), destination=get("bits_uop_pdest"),
                  store_set_hit=bool(get("bits_uop_storeSetHit")), wait_sq=sq(prefix + "bits_uop_waitSqIdx_"),
                  load_wait=bool(get("bits_uop_loadWaitBit")), strict=bool(get("bits_uop_loadWaitStrict")),
                  exceptions=sum(get(f"bits_uop_exceptionVec_{bit}") << bit for bit in SOURCE_EXCEPTION_BITS))
        req = Enqueue(bool(get("valid")), uop, get("bits_vaddr"), get("bits_mask"), bool(get("bits_nc")),
                      bool(get("bits_specialModeEligible")), bool(get("bits_specialModeRequest")), bool(get("bits_isvec")),
                      get("bits_alignedType"), bool(get("bits_isLoadReplay")), bool(get("bits_handledByMSHR")), get("bits_schedIndex"),
                      get("bits_rep_info_mshr_id"), sq(prefix + "bits_rep_info_data_inv_sq_idx_"), sq(prefix + "bits_rep_info_addr_inv_sq_idx_"),
                      bool(get("bits_rep_info_last_beat")), bool(get("bits_rep_info_need_rep")),
                      sum(get(f"bits_rep_info_cause_{bit}") << bit for bit in range(13)), get("bits_rep_info_tlb_id"),
                      bool(get("bits_rep_info_tlb_full")), bool(get("bits_rep_info_rep_from_unalign_head")))
        enqueues.append(req)
    wakes = {}
    for name in ("storeAddrWakeup", "storeDataWakeup", "storeDataWrite"):
        suffix = "" if name == "storeDataWrite" else "sqIdx_"
        wakes[name] = tuple(StoreWakeup(bool(values[f"io_{name}_{lane}_valid"]), sq(f"io_{name}_{lane}_bits_" + suffix)) for lane in range(2))
    return Inputs(tuple(enqueues), tuple(bool(values[f"io_replay_{lane}_ready"]) for lane in range(3)),
                  wakes["storeAddrWakeup"], wakes["storeDataWakeup"], wakes["storeDataWrite"],
                  tuple(Refill(bool(values[f"io_loadWakeup_{lane}_valid"]), values[f"io_loadWakeup_{lane}_bits_mshrId"]) for lane in range(2)),
                  tuple(L2Hint(bool(values[f"io_l2_hint_{lane}_valid"]), values[f"io_l2_hint_{lane}_bits_sourceId"], bool(values[f"io_l2_hint_{lane}_bits_isKeyword"])) for lane in range(2)),
                  TlbHint(bool(values["io_tlb_hint_resp_valid"]), values["io_tlb_hint_resp_bits_id"], bool(values["io_tlb_hint_resp_bits_replay_all"])),
                  TlbHint(bool(values["io_fast_tlb_hint_valid"]), values["io_fast_tlb_hint_bits_id"]),
                  LqWakeup(bool(values["io_mmioWakeup_valid"]), lq("io_mmioWakeup_bits_")),
                  LqWakeup(bool(values["io_ncWakeup_valid"]), lq("io_ncWakeup_bits_")),
                  sq("io_stAddrReadySqPtr_"), sum(values[f"io_stAddrReadyVec_{i}"] << i for i in range(64)),
                  sq("io_stDataReadySqPtr_"), sum(values[f"io_stDataReadyVec_{i}"] << i for i in range(64)),
                  sq("io_sqDeqPtr_"), sq("io_physicalUpperSqIdx_"), bool(values["io_sqEmpty"]), lq("io_ldWbPtr_"),
                  bool(values["io_rarFull"]), bool(values["io_rawFull"]), rob("io_robHeadPtr_"),
                  Redirect(bool(values["io_redirect_valid"]), rob("io_redirect_bits_robIdx_"), bool(values["io_redirect_bits_level"])), bool(values["reset"]))


class Ports:
    def __init__(self, dut):
        self.dut = dut
        self.inputs, self.outputs = {}, {}
        def walk(node, names=()):
            if "Pin" in node:
                name = "_".join(names)
                if name != "clock":
                    (self.inputs if node["Pin"] == "input" else self.outputs)[name] = getattr(dut, name)
            else:
                for name, child in node.items():
                    if isinstance(child, dict):
                        walk(child, (*names, name))
        walk(json.loads((ROOT / "dut/load_queue_replay/signals.json").read_text()))
        assert set(encode(Inputs())) == set(self.inputs) and len(self.inputs) == 400

    def sample(self, event):
        values = {name: signal.U() for name, signal in self.inputs.items()}
        return decode(values), {name: signal.U() for name, signal in self.outputs.items()}
